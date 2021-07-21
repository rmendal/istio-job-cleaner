# istio-job-cleaner
This container and the associated python file was created to solve the issue where we have jobs in Kubernetes that would never complete due to the istio-proxy sidecar running forever. The other containers in the pod needed to use the service mesh so we couldn't add a label to the pods to not inject the sidecar. Further, due to how our application stack works it would have been more difficult to edit our internal apps or containers to call out `curl -sf -XPOST localhost:15020/quitquitquit` to kill off the sidecar.

This container is deployed via a cronjob in Kubernetes and when run, pulls all runner jobs in the namespace defined in the python file and then pulls info for all runner pods in that namespace and checks all containers in the pod. If all containers are in a `Completed` state except for the istio sidecar then the pod is matched to it's job and that job is deleted.

If the job or non-istio container is in a state of running, active, failed, etc, then the job and pod are ignored.

This was built with the idea that the job names and pod names would have a common word in their names. The word in the job name does NOT have to match the common word in the pod name. This was an easier way to identify jobs/pods of interest and this app can be easily modified to check all jobs/pods if needed.

## How To Use
* Set the variables on lines 9-11.
* Build the container.
* Deploy it via cronjob