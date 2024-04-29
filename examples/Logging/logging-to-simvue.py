import logging
import click

from simvue import Handler, Run


@click.command
@click.option("--ci", is_flag=True, default=False)
def simvue_logger_demo(ci: bool) -> None:
    with Run() as run:
        run.init(
            tags=["logging"],
            folder="/simvue_client_demos",
            description="Logging test",
            ttl=60 * 60 if ci else -1,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        sth = Handler(run)
        logger.addHandler(sth)

        logger.info("This is a Simvue logging test")
