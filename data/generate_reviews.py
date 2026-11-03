"""Generate the synthetic FreshKart review dataset used by SignalSift.

FreshKart is a fictional 10-minute grocery delivery app. The reviews are
synthetic, modelled on the kinds of complaints and praise that appear in public
app-store reviews of quick-commerce apps. Two incidents are planted on purpose
so the alerting and prioritisation can be validated against a known truth:

* App v4.2 (released 18 Aug 2026) shipped a UPI payment bug that mostly hits Android.
* A new handling fee went live on 1 Jul 2026 and fee complaints rose.

The ``gold_theme`` column records which theme generated each review. The
pipeline never trains on it; it is only used to score clustering quality.

Usage:
    python data/generate_reviews.py --seed 7 --out data/reviews.csv
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

START = date(2026, 4, 1)
END = date(2026, 9, 30)
HANDLING_FEE_LAUNCH = date(2026, 7, 1)
V42_RELEASE = date(2026, 8, 18)
RELEASES = [(date(2026, 4, 1), "4.0"), (date(2026, 6, 2), "4.1"), (V42_RELEASE, "4.2")]
PLATFORM_SHARE = {"Android": 0.72, "iOS": 0.28}

CITIES = {
    "Bengaluru": ("Tier 1", 0.20), "Mumbai": ("Tier 1", 0.15), "Delhi": ("Tier 1", 0.15),
    "Hyderabad": ("Tier 1", 0.12), "Pune": ("Tier 1", 0.08), "Chennai": ("Tier 1", 0.08),
    "Jaipur": ("Tier 2", 0.06), "Lucknow": ("Tier 2", 0.06), "Indore": ("Tier 2", 0.05),
    "Kochi": ("Tier 2", 0.05),
}
ITEMS = ["milk", "bread", "eggs", "vegetables", "atta", "fruits", "curd", "paneer",
         "rice", "coffee", "baby diapers", "chips", "cooking oil", "bananas"]
AMOUNTS = [149, 236, 389, 512, 799, 1240, 1875]

# daily_rate = expected reviews per day across all platforms before incidents.
# ratings = probability of a 1..5 star rating for this theme.
THEMES: dict[str, dict] = {
    "delivery_delay": {
        "daily_rate": 3.0,
        "ratings": [0.40, 0.33, 0.16, 0.08, 0.03],
        "templates": [
            "Delivery promised in 10 minutes but it came late after {mins} minutes",
            "Late delivery again in {city}, waited {mins} minutes for my {item}",
            "Delivery ETA keeps changing and the rider is always late",
            "The 10 minute delivery promise is fake, my {item} came {mins} minutes late",
            "Rider got stuck and the delivery was late by {mins} minutes",
            "Late delivery every single time, the tracking map shows the rider not moving",
            "Delivery is never on time in {city}, the ETA is just a guess",
            "Ordered {item} for breakfast and the delivery came {mins} minutes late",
        ],
    },
    "payment_failure": {
        "daily_rate": 1.1,
        "ratings": [0.58, 0.26, 0.10, 0.04, 0.02],
        "templates": [
            "UPI payment failed but money got deducted, Rs {amount} not credited back",
            "UPI payment keeps failing at checkout, tried {n} times",
            "Money debited twice for one order of Rs {amount} and the payment shows failed",
            "After the latest update the UPI payment screen hangs and the payment fails",
            "Payment failed error every time I pay with UPI, card payment works though",
            "Checkout payment stuck on processing then failed, amount deducted",
            "UPI app does not open from checkout so the payment fails",
            "Payment failed in the app but bank says Rs {amount} debited via UPI",
        ],
    },
    "app_performance": {
        "daily_rate": 2.0,
        "ratings": [0.35, 0.30, 0.20, 0.10, 0.05],
        "templates": [
            "App crashes every time I open the cart",
            "The app is very slow and freezes on the home screen",
            "App keeps crashing after login, had to reinstall {n} times",
            "App freezes on the OTP screen and then crashes",
            "Search is slow and the app hangs while loading products",
            "App crashes when I try to add {item} to cart",
            "Too slow and laggy, the app takes forever to load and then crashes",
            "Screen goes blank and the app crashes and freezes",
        ],
    },
    "refund_support": {
        "daily_rate": 1.8,
        "ratings": [0.45, 0.32, 0.14, 0.06, 0.03],
        "templates": [
            "Refund for missing {item} still not received after {n} days, support is useless",
            "Customer support chat is a useless bot, no human agent ever replies about my refund",
            "Raised a refund complaint {n} days ago and customer support never responded",
            "Support promised a refund in 24 hours but it has been {n} days",
            "Support agent closed my refund ticket without solving the issue",
            "No way to talk to a real person in customer support about a refund",
            "Item was missing from my order and support rejected the refund request",
            "Customer support keeps sending the same copy paste reply, still no refund",
        ],
    },
    "fees_pricing": {
        "daily_rate": 1.4,
        "ratings": [0.25, 0.30, 0.28, 0.12, 0.05],
        "templates": [
            "Too many hidden charges, delivery fee plus handling fee plus small cart fee",
            "Prices are higher than the local kirana store, plus extra fee charges",
            "Handling fee of Rs {n}9 on every order is unfair",
            "Surge fee during rain makes it too expensive",
            "Small cart fee forces me to add items I do not need",
            "Prices for {item} are expensive and the fee charges keep changing",
            "Delivery fee and charges went up again, too expensive now",
            "New handling fee makes small orders very expensive",
        ],
    },
    "product_quality": {
        "daily_rate": 2.0,
        "ratings": [0.38, 0.32, 0.18, 0.08, 0.04],
        "templates": [
            "Received stale {item}, quality is very poor",
            "Got expired {item}, please check quality and expiry dates before packing",
            "The {item} was rotten and the quality was poor",
            "Poor quality, ordered fresh {item} but got a stale one",
            "Vegetables were not fresh at all, half of them rotten",
            "Packet of {item} was expired and damaged, poor quality check",
            "Quality of fruits and vegetables has dropped badly, many rotten",
            "Expired product delivered again, quality is a health risk",
        ],
    },
    "feature_requests": {
        "daily_rate": 1.6,
        "ratings": [0.05, 0.12, 0.38, 0.33, 0.12],
        "templates": [
            "Please add a dark mode option, would be a useful feature",
            "Please add Hindi and Tamil language option in the app",
            "Feature request: add an option to schedule delivery for the morning",
            "Please add a feature to save my weekly shopping list",
            "Add a one tap reorder option for my usual items, would love this feature",
            "Feature request: add an option to split the bill with flatmates",
            "Please add a regional language option for my parents",
            "Would be great to add a feature to set a monthly grocery budget",
        ],
    },
    "praise": {
        "daily_rate": 3.2,
        "ratings": [0.01, 0.02, 0.07, 0.30, 0.60],
        "templates": [
            "Super quick, got fresh {item} in 9 minutes, so convenient",
            "Fresh {item} and great discounts, very convenient",
            "Best grocery app in {city}, quick and reliable",
            "Lifesaver for late night cravings, quick and convenient every time",
            "Great offers and smooth experience, my go to grocery app",
            "Polite delivery partner and fresh products, very convenient",
            "Very convenient and quick, I do all my grocery shopping here now",
            "Quick service, fresh {item} and good offers, highly recommend",
        ],
    },
}

# Tone phrases carry sentiment but are only present on some reviews, and
# sometimes drift one star from the rating, so the text-to-rating link stays
# realistically noisy.
TONE = {
    1: {"prefix": ["Worst experience ever.", "Absolutely terrible.", "Pathetic service.", "Very disappointed.", ""],
        "suffix": ["Uninstalling.", "Never ordering again.", "Please fix this.", "Third time this week.", ""]},
    2: {"prefix": ["Not happy.", "Quite frustrating.", "Disappointing.", ""],
        "suffix": ["Please fix this.", "Hope the team looks into it.", "Expected better.", ""]},
    3: {"prefix": ["It's okay.", "Average experience.", "Mixed feelings.", ""],
        "suffix": ["Otherwise fine.", "Could be better.", ""]},
    4: {"prefix": ["Good app overall.", "Mostly happy.", "Pretty good.", ""],
        "suffix": ["Still a good app.", "Keep improving.", ""]},
    5: {"prefix": ["Love this app!", "Excellent service!", "Amazing!", ""],
        "suffix": ["Keep it up!", "Five stars.", "Thank you team!", ""]},
}


def app_version(day: date) -> str:
    version = RELEASES[0][1]
    for released_on, name in RELEASES:
        if day >= released_on:
            version = name
    return version


def incident_multiplier(theme: str, day: date, platform: str) -> float:
    multiplier = 1.0
    if theme == "payment_failure" and day >= V42_RELEASE:
        multiplier *= 4.0 if platform == "Android" else 1.3
    if theme == "fees_pricing" and day >= HANDLING_FEE_LAUNCH:
        multiplier *= 1.9
    return multiplier


def compose_review(theme: str, rating: int, city: str, rng: np.random.Generator) -> str:
    template = rng.choice(THEMES[theme]["templates"])
    body = template.format(
        mins=rng.integers(35, 96), item=rng.choice(ITEMS), city=city,
        amount=rng.choice(AMOUNTS), n=rng.integers(2, 6),
    )
    tone_rating = int(np.clip(rating + rng.choice([-1, 0, 0, 0, 1]), 1, 5))
    prefix = rng.choice(TONE[tone_rating]["prefix"]) if rng.random() < 0.6 else ""
    suffix = rng.choice(TONE[rating]["suffix"]) if rng.random() < 0.4 else ""
    return " ".join(part for part in (prefix, body + ".", suffix) if part)


def generate(seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    city_names = list(CITIES)
    city_weights = np.array([CITIES[c][1] for c in city_names])
    city_weights = city_weights / city_weights.sum()

    rows = []
    day = START
    while day <= END:
        version = app_version(day)
        for platform, platform_share in PLATFORM_SHARE.items():
            for theme, spec in THEMES.items():
                expected = spec["daily_rate"] * platform_share * incident_multiplier(theme, day, platform)
                for _ in range(rng.poisson(expected)):
                    city = str(rng.choice(city_names, p=city_weights))
                    rating = int(rng.choice([1, 2, 3, 4, 5], p=spec["ratings"]))
                    rows.append({
                        "date": day.isoformat(),
                        "platform": platform,
                        "app_version": version,
                        "city": city,
                        "city_tier": CITIES[city][0],
                        "rating": rating,
                        "text": compose_review(theme, rating, city, rng),
                        "gold_theme": theme,
                    })
        day += timedelta(days=1)

    df = pd.DataFrame(rows).sort_values(["date", "platform"], kind="stable").reset_index(drop=True)
    df.insert(0, "review_id", [f"R{i:05d}" for i in range(1, len(df) + 1)])
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("reviews.csv"))
    args = parser.parse_args()
    df = generate(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df):,} reviews to {args.out}")


if __name__ == "__main__":
    main()
