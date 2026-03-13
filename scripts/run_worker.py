#!/usr/bin/env python3
"""Entry point for the CV inference worker."""

import asyncio
import logging

from icast_cv.worker.inference import run_worker


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
