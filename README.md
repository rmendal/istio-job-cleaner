# istio-job-cleaner
This container and the associated python file was created to solve the issue/edge case where we have jobs in Kubernetes that would never complete due to the istio-proxy sidecar running forever. The other containers in the pod needed to use the service mesh so we couldn't add a label to the pods to not inject the sidecar. Further, due to how our application stack works it would have been more difficult to edit our internal apps or containers to call out `curl -sf -XPOST localhost:15020/quitquitquit` to kill off the sidecar. Additionally, at the time of this writing the KEP that would have solved this has been [scrapped](https://github.com/kubernetes/enhancements/issues/753).

This container is deployed via a cronjob in Kubernetes with an env var for the required namespace and when run, pulls all jobs and pods in the namespace based on the common word shared among all our pods, in this case the word `runner`, and then checks all containers in those pods. If all containers are in a `Completed` state except for the istio-proxy sidecar then the pod is matched to it's job and that job is deleted. This has been tested with 200+ simultaneous jobs.

If the job or non-istio container(s) are in a state of running, active, failed, etc, then the job and pod are ignored.

This was built with the idea that the job names and pod names would have a common word in their names. The word in the job name does NOT have to match the common word in the pod name. This was an easier way to identify jobs/pods of interest and this app can be easily modified to check all jobs/pods if needed.

It's worth noting that this was built in a hurry and the code is ugly and while it tries to follow PEP 8 standards it runs afoul of the line length standard. I'll refactor this eventually or just rewrite this in Go.
## How To Use
* Search for `runner` in the code and adjust for your needs.
* Build the container.
* Create a service account, role and role binding so the container can get/list/delete jobs/pods.
* Deploy it via cronjob, an example one is in the `example` dir.