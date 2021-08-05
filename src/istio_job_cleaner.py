from kubernetes import client, config
from json import loads
from sys import exit
from threading import Thread

config.load_incluster_config()
# Use the below for local testing
# config.load_kube_config()

v1 = client.CoreV1Api()
batchv1 = client.BatchV1Api()
namespace = "zn-dev"
common_job_name = "runner"
common_pod_name = "runner"


def process_jobs():
    """
    This pulls all jobs in the declared namespace that have "runner"
    in their name and are actively running, formats their names and
    UIDs into a dict for further processing in the handle_jobs function

    The kubernetes library returns an http response on all api calls.
    The data appears as JSON but isn't actually valid. It required a
    lot of lengthy conditionals and "get" methods with occasional
    references to list indices. It's not pretty and should be refactored
    in the near future.

    returns: job_dict, dictionary of active runner jobs where
    key: job-name, value: job-uid
    """
    job_list = list()
    jobs_obj = batchv1.list_namespaced_job(namespace=namespace,
                                           _preload_content=False,
                                           limit=1,
                                           )
    jobs_json = loads(jobs_obj.data)

    # If no jobs or no jobs, exit. Else add those jobs to the list
    if not jobs_json.get("items", {}):
        exit(0)
    else:
        job_list.append(jobs_json)

    # Loop over the http response so all jobs are added to the list
    # and aren't just one long http response.
    threads = []
    while job_list:
        job = job_list.pop()
        job_items = job.get("items", [{}])[0]
        job_metadata = job_items.get("metadata", {})
        job_status = job_items.get("status")

        job_dict = dict()
        if (common_job_name in job_metadata.get("name") and job_status.get("active")):
            job_dict[job_metadata.get("name")] = job_metadata.get("uid")

        thread = Thread(target=handle_jobs, args=(job_dict, ))
        threads.append(thread)
        thread.start()

        if jobs_json.get("metadata", {}).get("continue"):
            jobs_obj = batchv1.list_namespaced_job(
                namespace=namespace,
                _preload_content=False, limit=1,
                _continue=jobs_json.get("metadata", {}).get("continue")
            )
            jobs_json = loads(jobs_obj.data)
            job_list.append(jobs_json)

    # keeps the threads active until we kill them
    for thr in threads:
        thr.join()


def handle_jobs(jobs):
    """
    Creates a list of all pods in the namespace with "runner" in the
    name, iterates over the containers in the pod to ensure only
    istio-proxy is running and the others are completed, not failed
    or in some other state, then matches the pod owner uid to the
    job uid passed into it from the above function and if a match
    is found, deletes the job.
    """
    pod_list = list()
    pods_obj = v1.list_namespaced_pod(
        namespace=namespace,
        _preload_content=False,
        limit=1,
    )
    pods_json = loads(pods_obj.data)
    pod_list.append(pods_json)

    while pod_list:
        pod = pod_list.pop()
        pod_items = pod.get("items", [{}])[0]
        pod_metadata = pod_items.get("metadata", {})

        if common_pod_name in pod_metadata.get("name"):
            count = 0

            container_statuses_list = pod_items.get("status", {}).get("containerStatuses", [])
            for j, container_statuses in enumerate(container_statuses_list):
                terminated_meta = container_statuses.get("state", {}).get("terminated", {})
                name = container_statuses.get("name")
                finishedAt = terminated_meta.get("finishedAt")
                exitCode = terminated_meta.get("exitCode")

                if ("istio-proxy" not in name and finishedAt and exitCode == 0):
                    count += 1
                    if count == (len(container_statuses_list) - 1):
                        for k, v in jobs.items():
                            if pod_metadata.get("ownerReferences", [{}])[0].get("uid") == v:
                                print(f"delete called on {k} - {name}, {finishedAt}, {exitCode}")
                                batchv1.delete_namespaced_job(
                                    name=k,
                                    namespace=namespace,
                                    propagation_policy="Background",)
                                return
                            else:
                                continue
                    else:
                        continue
                else:
                    continue

        if pod.get("metadata", {}).get("continue"):
            pods_obj = v1.list_namespaced_pod(
                namespace=namespace,
                _preload_content=False,
                limit=1,
                _continue=pod.get("metadata", {}).get("continue"),
            )
            pods_json = loads(pods_obj.data)
            pod_list.append(pods_json)


if __name__ == '__main__':
    process_jobs()
