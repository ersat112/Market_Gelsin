import sys
from pathlib import Path
from typing import Dict, Union

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from nationwide_platform.planner import build_default_targets, summarize_targets
    from nationwide_platform.storage import (
        DEFAULT_DB_PATH,
        connect,
        initialize_schema,
        seed_adapter_onboarding_backlog,
        seed_city_collection_program,
        seed_city_controlled_flow_plan,
        seed_city_coverage_status,
        seed_city_discovery_queries,
        seed_cities,
        seed_city_discovery_tasks,
        seed_local_market_candidates,
        seed_market_adapter_readiness,
        seed_market_refresh_policy,
        seed_markets,
        seed_targets,
    )
else:
    from .planner import build_default_targets, summarize_targets
    from .storage import (
        DEFAULT_DB_PATH,
        connect,
        initialize_schema,
        seed_adapter_onboarding_backlog,
        seed_city_collection_program,
        seed_city_controlled_flow_plan,
        seed_city_coverage_status,
        seed_city_discovery_queries,
        seed_cities,
        seed_city_discovery_tasks,
        seed_local_market_candidates,
        seed_market_adapter_readiness,
        seed_market_refresh_policy,
        seed_markets,
        seed_targets,
    )


def bootstrap_database(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> Dict[str, int]:
    targets = build_default_targets()
    with connect(db_path) as connection:
        initialize_schema(connection)
        seed_cities(connection)
        seed_markets(connection)
        seed_targets(connection, targets)
        seed_city_collection_program(connection)
        seed_market_refresh_policy(connection)
        seed_city_discovery_tasks(connection)
        seed_city_discovery_queries(connection)
        seed_city_coverage_status(connection)
        seed_city_controlled_flow_plan(connection)
        seed_local_market_candidates(connection)
        seed_market_adapter_readiness(connection)
        seed_adapter_onboarding_backlog(connection)
    return summarize_targets(targets)


if __name__ == "__main__":
    summary = bootstrap_database()
    print("Turkiye geneli crawl target planlamasi tamamlandi.")
    for market_key, target_count in summary.items():
        print(f"- {market_key}: {target_count} il hedefi")
