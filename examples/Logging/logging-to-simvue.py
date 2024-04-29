import logging

from simvue import Handler, Run

if __name__ == "__main__":
    run = Run()

    run.init(
        tags=["logging"], folder="/simvue_client_demos", description="Logging test"
    )

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    sth = Handler(run)
    logger.addHandler(sth)

    logger.info("This is a Simvue logging test")

    run.close()
