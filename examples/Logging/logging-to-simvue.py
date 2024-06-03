import logging
import click

from simvue import Handler, Run


@click.command
@click.option("--ci", is_flag=True, default=False)
def simvue_logger_demo(ci: bool) -> None:
    with Run() as run:
        run.init(
            tags=["logging", "simvue_client_examples"],
            folder="/simvue_client_demos",
            description="Logging test",
            retention_period="1 hour" if ci else None,
            visibility="tenant" if ci else None,
        )

        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        sth = Handler(run)
        logger.addHandler(sth)

        logger.info("This is a Simvue logging test")
