from kubernetes import client, config
from json import loads
import os

config.load_incluster_config()
# Use the below for local testing
# config.load_kube_config()

v1 = client.CoreV1Api()
batchv1 = client.BatchV1Api()

namespace = os.getenv("NAMESPACE")


def process_pods():
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
        limit=100,
    )
    pods_json = loads(pods_obj.data)
    metadata = pods_json.get("metadata", {})
    pods_item = pods_json.get("items", [{}])
    pod_list.extend(pods_item)

    pods_checked = 0
    delete_requests = 0
    while pod_list:
        pods_checked += 1
        pod = pod_list.pop()
        if not pod_list and metadata.get("continue"):
            pods_obj = v1.list_namespaced_pod(
                namespace=namespace,
                _preload_content=False,
                limit=100,
                _continue=metadata.get("continue"),
            )
            pods_json = loads(pods_obj.data)
            metadata = pods_json.get("metadata", {})
            pods_item = pods_json.get("items", [{}])
            pod_list.extend(pods_item)

        pod_metadata = pod.get("metadata", {})
        job_uid = pod_metadata.get("ownerReferences", [{}])[0].get("uid")
        job_name = pod_metadata.get("ownerReferences", [{}])[0].get("name")
        pod_status = pod.get("status", {})
        pod_phase = pod.get("status", {}).get("phase")
        containerStatuses = pod_status.get("containerStatuses", {})
        containers = []

        is_pod_succeeded = pod_phase.lower() == "succeeded"
        is_runner_job = False
        is_istio_running = True
        is_job_finished = True
        main_container_name = None
        finishedAt = None
        exitCode = None

        for container in containerStatuses:
            is_runner_job = "-runner" in container.get("name") or is_runner_job

            if "istio" in container.get("name"):
                startedAt = container.get("state", {}).get("running", {}).get("startedAt")
                is_istio_running = startedAt is not None
            elif container.get("name") in job_name:
                main_container_name = container.get("name")
                finishedAt = container.get("state", {}).get("terminated", {}).get("finishedAt")
                reason = container.get("state", {}).get("terminated", {}).get("reason")
                exitCode = container.get("state", {}).get("terminated", {}).get("exitCode")

                is_container_finished = finishedAt is not None and exitCode == 0 and reason.lower() == "completed"
                is_job_finished = is_container_finished and is_job_finished

            item = (container.get("name"), container.get("state"))
            containers.append(item)

        if not job_uid:
            continue
        elif (main_container_name and is_runner_job and is_istio_running and is_job_finished) or is_pod_succeeded:
            delete_requests += 1
            print(f"container_name: {main_container_name}")
            print(f"job_name: {job_name}")
            print(f"job_uid: {job_uid}")
            print(f"is_pod_succeeded: {is_pod_succeeded}")
            print(f"is_runner_job: {is_runner_job}")
            print(f"is_istio_running: {is_istio_running}")
            print(f"is_job_finished: {is_job_finished}")
            print(f"delete called on {job_name} - {pod_phase} - {finishedAt}, {exitCode}")
            try:
                batchv1.delete_namespaced_job(
                    name=job_name,
                    namespace=namespace,
                    propagation_policy="Background",)
            except Exception as err:
                pass

    print(f"*** pods analyzed {pods_checked} & delete requests made {delete_requests} ***")


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
                                           limit=100,
                                           )
    jobs_json = loads(jobs_obj.data)
    metadata = jobs_json.get("metadata", {})
    job_item = jobs_json.get("items", [{}])
    job_list.extend(job_item)

    jobs_checked = 0
    delete_requests = 0
    while job_list:
        jobs_checked += 1
        job = job_list.pop()
        if not job_list and metadata.get("continue"):
            jobs_obj = batchv1.list_namespaced_job(
                namespace=namespace,
                _preload_content=False,
                limit=100,
                _continue=metadata.get("continue")
            )
            jobs_json = loads(jobs_obj.data)
            metadata = jobs_json.get("metadata", {})
            job_item = jobs_json.get("items", [{}])
            job_list.extend(job_item)

        completionTime = job.get("status", {}).get("completionTime")
        job_name = job.get("metadata", {}).get("name")
        if completionTime:
            delete_requests += 1
            print(f"delete called on {job_name} - {completionTime}")
            try:
                pass
                batchv1.delete_namespaced_job(
                    name=job_name,
                    namespace=namespace,
                    propagation_policy="Background",)
            except:
                pass

    print(f"*** jobs analyzed {jobs_checked} & delete requests made {delete_requests} ***")


if __name__ == '__main__':
    process_pods()
    process_jobs()
