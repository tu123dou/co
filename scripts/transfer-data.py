"""数据迁移脚本：以压缩 JSONL 导出和恢复业务数据，不输出数据库凭据。"""

import argparse
from datetime import date, datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path

from sqlalchemy import Integer, create_engine, func, insert, select, text
from sqlalchemy.engine import make_url

from app.config import settings
from app.schema import metadata


def encode(value):
    """把 JSON 不支持的数据库类型编码为带类型标记的对象。"""
    if isinstance(value, datetime):
        return {"$type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"$type": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"$type": "decimal", "value": str(value)}
    raise TypeError(type(value).__name__)


def decode(value):
    """将备份中的类型标记还原为 Python 数据类型。"""
    if value.get("$type") == "datetime":
        return datetime.fromisoformat(value["value"])
    if value.get("$type") == "date":
        return date.fromisoformat(value["value"])
    if value.get("$type") == "decimal":
        return Decimal(value["value"])
    return value


def legacy_tables():
    """返回需要搬迁的数据表，排除可重新生成的向量和审计数据。"""
    return [table for table in metadata.sorted_tables if table.name not in {
        "semantic_documents", "semantic_chunks", "embedding_jobs", "retrieval_events"
    }]


def export_data(path):
    """按外键安全顺序把应用和业务数据写入压缩文件。"""
    source = create_engine(settings().database_url)
    counts = {}
    with source.connect() as conn, gzip.open(path, "wt", encoding="utf-8") as output:
        output.write(json.dumps({"format": 1, "tables": [table.fullname for table in legacy_tables()]}) + "\n")
        for table in legacy_tables():
            count = 0
            for row in conn.execute(select(table)).mappings():
                output.write(json.dumps({"table": table.fullname, "row": dict(row)}, ensure_ascii=False, default=encode) + "\n")
                count += 1
            counts[table.fullname] = count
    print(json.dumps({"backup": str(path), "counts": counts}, ensure_ascii=False))


def import_data(path, target_url):
    """仅向空数据库恢复数据，并同步自增主键序列。"""
    target = create_engine(target_url)
    tables = {table.fullname: table for table in legacy_tables()}
    rows = {name: [] for name in tables}
    with gzip.open(path, "rt", encoding="utf-8") as source:
        header = json.loads(next(source))
        if header.get("format") != 1:
            raise RuntimeError("不支持的备份格式")
        for line in source:
            item = json.loads(line, object_hook=decode)
            rows[item["table"]].append(item["row"])
    with target.begin() as conn:
        existing = sum(conn.scalar(select(func.count()).select_from(table)) for table in tables.values())
        if existing:
            raise RuntimeError("目标数据库已有业务数据，拒绝覆盖")
        for table in legacy_tables():
            batch = rows[table.fullname]
            for offset in range(0, len(batch), 1000):
                conn.execute(insert(table), batch[offset : offset + 1000])
            integer_pk = next(
                (
                    column
                    for column in table.primary_key
                    if isinstance(column.type, Integer)
                    and (column.autoincrement is True or column.autoincrement == "auto")
                ),
                None,
            )
            if integer_pk is not None and batch:
                conn.execute(
                    text("SELECT setval(pg_get_serial_sequence(:table_name, :column_name), :value, true)"),
                    {"table_name": table.fullname, "column_name": integer_pk.name, "value": max(row[integer_pk.name] for row in batch)},
                )
    print(json.dumps({"restored": str(path), "counts": {name: len(value) for name, value in rows.items()}}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("path", type=Path)
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("path", type=Path)
    import_parser.add_argument("--target-port", type=int, default=54330)
    args = parser.parse_args()
    if args.command == "export":
        export_data(args.path)
    else:
        target_url = make_url(settings().database_url).set(host="127.0.0.1", port=args.target_port)
        import_data(args.path, target_url)


if __name__ == "__main__":
    main()
