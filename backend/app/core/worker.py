from rq import SimpleWorker
from app.core.queue import redis_conn, job_queue

if __name__ == "__main__":
    worker = SimpleWorker([job_queue], connection=redis_conn)
    worker.work()