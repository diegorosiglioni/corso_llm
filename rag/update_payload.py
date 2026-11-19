"""python -m rag.update_payload: writes `has_doses` on the points already in the collection.

The field is computed from the `text` saved in each point (rule in rag/doses.py) and written with
set_payload by ID, so the embeddings are not computed again (requirement of the exercise) and LM
Studio is not contacted; the book and the chunking variables are not needed either: exactly the
points in the collection are updated. Repeatable; an interrupted run is completed by running it
again. Creates the `has_doses` index if the collection does not have it."""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rag.config import ConfigError, configure_logging, load_config
from rag.doses import has_doses
from rag.store import (
    StoreError, connect, count_missing, ensure_indexes, iter_texts, require_points, set_field,
)

FIELD = "has_doses"


@dataclass(frozen=True)
class UpdateReport:
    points: int
    updated: int
    with_doses: int
    missing: int


def run_update(client, collection: str) -> UpdateReport:
    """Computes `has_doses` for every point and writes it (one set_field per value, in batches);
    `missing` counts the points still without the field afterwards."""
    points = require_points(client, collection)
    ensure_indexes(client, collection)
    ids: dict[bool, list[str]] = {True: [], False: []}
    for point_id, text in iter_texts(client, collection):
        ids[has_doses(text)].append(point_id)
    for value, value_ids in ids.items():
        set_field(client, collection, FIELD, value, value_ids)
    return UpdateReport(
        points=points,
        updated=len(ids[True]) + len(ids[False]),
        with_doses=len(ids[True]),
        missing=count_missing(client, collection, FIELD),
    )


def format_report(report: UpdateReport) -> str:
    return (
        f"Punti: {report.points} · aggiornati: {report.updated} · con dosi: {report.with_doses} · "
        f"senza campo: {report.missing}"
    )


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rag.update_payload",
        description="Aggiunge has_doses ai punti già indicizzati, senza ricalcolare gli embedding.",
    )
    parser.parse_args(argv)
    try:
        config = load_config(env)
        configure_logging(config.log_level)
        client = connect(config.qdrant_url)
        try:
            report = run_update(client, config.collection)
        finally:
            client.close()
    except (ConfigError, StoreError) as error:
        print(error, file=sys.stderr)
        return 1
    print(format_report(report))
    if report.missing > 0:
        print(
            f"{report.missing} punti senza has_doses dopo l'aggiornamento: rieseguire "
            "python -m rag.update_payload",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
