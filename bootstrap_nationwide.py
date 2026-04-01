from nationwide_platform.bootstrap import bootstrap_database
from nationwide_platform.city_rollout import summarize_city_controlled_flow_plans


if __name__ == "__main__":
    summary = bootstrap_database()
    print("Turkiye geneli crawl target planlamasi tamamlandi.")
    for market_key, target_count in summary.items():
        print(f"- {market_key}: {target_count} il hedefi")
    print("Kontrollu canli akis asama ozeti:")
    for stage, count in sorted(summarize_city_controlled_flow_plans().items()):
        print(f"- {stage}: {count} il")
