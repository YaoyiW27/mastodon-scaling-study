from locust import HttpUser, task, between

class MastodonUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def home(self):
        self.client.get("/")

    @task(3)
    def explore(self):
        self.client.get("/explore")

    @task(2)
    def about(self):
        self.client.get("/about")

    @task(1)
    def health(self):
        self.client.get("/health")