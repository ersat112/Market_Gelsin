import sys

from nationwide_platform.normalization import normalize_barcode
from nationwide_platform.storage import connect


def main() -> int:
    if len(sys.argv) < 2:
        print("Kullanim: python3 lookup_barcode.py <barcode>")
        return 1

    barcode = normalize_barcode(sys.argv[1])
    if barcode is None:
        print("Gecersiz barkod formati. 8/12/13/14 haneli bir barkod girin.")
        return 1

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT
                o.market_key,
                c.name,
                o.display_name,
                o.listed_price,
                o.promo_price,
                o.availability,
                o.observed_at
            FROM effective_offers o
            JOIN cities c ON c.plate_code = o.city_plate_code
            WHERE o.source_barcode = ?
            ORDER BY o.observed_at DESC, o.listed_price ASC
            """,
            (barcode,),
        ).fetchall()

    if not rows:
        print(f"{barcode} icin kayitli market teklifi bulunamadi.")
        return 0

    print(f"{barcode} icin {len(rows)} teklif bulundu:")
    for market_key, city_name, display_name, listed_price, promo_price, availability, observed_at in rows:
        active_price = promo_price if promo_price is not None else listed_price
        print(
            f"- {city_name} | {market_key} | {display_name} | fiyat={active_price} TL | "
            f"stok={availability or 'unknown'} | {observed_at}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
