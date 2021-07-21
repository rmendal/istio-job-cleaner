from kubernetes import client, config
from json import loads
from sys import exit

config.load_incluster_config()

v1 = client.CoreV1Api()
batchv1 = client.BatchV1Api()
namespace = ""
common_job_name = ""
common_pod_name = ""


def get_jobs():
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
    job_dict = dict()
    jobs_obj = batchv1.list_namespaced_job(namespace=namespace,
                                           _preload_content=False, limit=1)
    jobs_json = loads(jobs_obj.data)

    # If no jobs or no jobs, exit. Else add those jobs to the list
    if not jobs_json.get("items"):
        exit(0)
    else:
        job_list.append(jobs_json)

    # Loop over the http response so all jobs are added to the list
    # and aren't just one long http response.
    while jobs_json.get("metadata", {}).get("continue") is not None:
        jobs_obj = batchv1.list_namespaced_job(namespace=namespace,
                                               _preload_content=False, limit=1,
                                               _continue=jobs_json.get("metadata", {}).get("continue"))
        jobs_json = loads(jobs_obj.data)
        job_list.append(jobs_json)

    # Pull runner specific jobs out of the list and add their name, uid to a dict.
    for i in range(len(job_list)):
        if (common_job_name in job_list[i].get("items")[0].get("metadata", {}).get("name") and
            job_list[i].get("items")[0].get("status", {}).get("active") is not None):
            job_dict[job_list[i].get("items")[0].get("metadata", {}).get("name")] = job_list[i].get("items")[0].get("metadata", {}).get("uid")

    return(job_dict)


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
    pods_obj = v1.list_namespaced_pod(namespace=namespace, _preload_content=False, limit=1)
    pods_json = loads(pods_obj.data)
    pod_list.append(pods_json)
    while pods_json.get("metadata", {}).get("continue") is not None:
        pods_obj = v1.list_namespaced_pod(namespace=namespace, _preload_content=False,
                                          limit=1, _continue=pods_json.get("metadata", {}).get("continue"))
        pods_json = loads(pods_obj.data)
        pod_list.append(pods_json)

    for i in range(len(pod_list)):
        if common_pod_name in pod_list[i].get("items")[0].get("metadata", {}).get("name"):
            count = 0
            for j in range(len(pod_list[i].get("items")[0].get("status", {}).get("containerStatuses"))):
                if ("istio-proxy" not in pod_list[i].get("items")[0].get("status", {}).get("containerStatuses")[j].get("name") and
                    pod_list[i].get("items")[0].get("status", {}).get("containerStatuses")[j].get("state", {}).get("terminated", {}).get("finishedAt") is not None
                    and pod_list[i].get("items")[0].get("status", {}).get("containerStatuses")[j].get("state", {}).get("terminated", {}).get("exitCode") == 0):
                    count += 1
                    if count == (len(pod_list[i].get("items")[0].get("status", {}).get("containerStatuses")) - 1):
                        for k, v in jobs.items():
                            if pod_list[i].get("items")[0].get("metadata", {}).get("ownerReferences")[0].get("uid") == v:
                                print(f"delete called on {k}")
                                batchv1.delete_namespaced_job(name=k, namespace=namespace, propagation_policy="Background")
                            else:
                                continue
                    else:
                        continue
                else:
                    continue
        else:
            continue


def main():
    jobs = get_jobs()
    handle_jobs(jobs)


if __name__ == '__main__':
    main()
