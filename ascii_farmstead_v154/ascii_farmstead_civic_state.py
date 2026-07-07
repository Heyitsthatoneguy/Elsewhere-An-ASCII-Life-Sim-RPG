from __future__ import annotations

"""UI-free persistence sanitizers for civic economy save data."""

import copy
from typing import Dict


BUSINESS_TYPES = {
    "general_store",
    "market_stall",
    "inn",
    "clinic",
    "carpenter",
    "workshop",
    "library",
}
BUSINESS_STRATEGIES = {
    "Balanced",
    "Local Goods",
    "Growth",
    "Trade",
}


def _clean_dict(value: object) -> Dict[str, object]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def sanitize_player_properties(value: object) -> Dict[str, Dict[str, object]]:
    clean: Dict[str, Dict[str, object]] = {}
    for raw_id, raw in _clean_dict(value).items():
        if not isinstance(raw, dict):
            continue
        property_id = str(raw_id or raw.get("id", "")).strip()
        town_key = str(raw.get("town_key", "")).strip()
        building_id = str(raw.get("building_id", "")).strip()
        if not property_id or not town_key or not building_id:
            continue
        clean[property_id] = {
            "id": property_id,
            "town_key": town_key,
            "building_id": building_id,
            "name": str(raw.get("name", "Town Residence")),
            "kind": str(raw.get("kind", "residence")),
            "purchase_price": max(0, int(raw.get("purchase_price", 0))),
            "purchased_day": str(raw.get("purchased_day", "")),
            "comfort": max(0, min(10, int(raw.get("comfort", 1)))),
            "built": bool(raw.get("built", False)),
            "upgrade_level": max(0, min(3, int(raw.get("upgrade_level", 0)))),
            "household_moved": bool(raw.get("household_moved", False)),
            "use_mode": (
                str(raw.get("use_mode", "Private"))
                if str(raw.get("use_mode", "Private"))
                in {"Private", "Guesthouse", "Rental"}
                else "Private"
            ),
            "furnishings_level": max(-1, min(3, int(raw.get("furnishings_level", -1)))),
            "original_residents_rehoused": max(
                0,
                int(raw.get("original_residents_rehoused", 0)),
            ),
            "lifetime_income": max(0, int(raw.get("lifetime_income", 0))),
            "last_income_ordinal": max(0, int(raw.get("last_income_ordinal", 0))),
        }
    return clean


def sanitize_player_businesses(value: object) -> Dict[str, Dict[str, object]]:
    clean: Dict[str, Dict[str, object]] = {}
    for raw_id, raw in _clean_dict(value).items():
        if not isinstance(raw, dict):
            continue
        business_id = str(raw_id or raw.get("id", "")).strip()
        town_key = str(raw.get("town_key", "")).strip()
        building_id = str(raw.get("building_id", "")).strip()
        type_id = str(raw.get("type_id", "")).strip()
        if not business_id or not town_key or not building_id or type_id not in BUSINESS_TYPES:
            continue
        strategy = str(raw.get("strategy", "Balanced"))
        if strategy not in BUSINESS_STRATEGIES:
            strategy = "Balanced"
        clean[business_id] = {
            "id": business_id,
            "town_key": town_key,
            "building_id": building_id,
            "type_id": type_id,
            "name": str(raw.get("name", "Player Business")),
            "purchase_price": max(0, int(raw.get("purchase_price", 0))),
            "purchased_day": str(raw.get("purchased_day", "")),
            "manager_resident_id": str(raw.get("manager_resident_id", "")),
            "employee_ids": [
                str(resident_id)
                for resident_id in raw.get("employee_ids", [])
                if str(resident_id or "").strip()
                and str(resident_id) != str(raw.get("manager_resident_id", ""))
            ][:8],
            "strategy": strategy,
            "wage_policy": (
                str(raw.get("wage_policy", "Standard"))
                if str(raw.get("wage_policy", "Standard"))
                in {"Standard", "Generous", "Training"}
                else "Standard"
            ),
            "supply_contract": (
                str(raw.get("supply_contract", "Reliable Supply"))
                if str(raw.get("supply_contract", "Reliable Supply"))
                in {"Reliable Supply", "Local Exports", "Essential Goods"}
                else "Reliable Supply"
            ),
            "last_income_ordinal": max(0, int(raw.get("last_income_ordinal", 0))),
            "lifetime_income": max(0, int(raw.get("lifetime_income", 0))),
            "upgrade_level": max(0, min(3, int(raw.get("upgrade_level", 0)))),
            "total_invested": max(0, int(raw.get("total_invested", 0))),
            "active": bool(raw.get("active", True)),
        }
    return clean


def sanitize_player_trade_routes(value: object) -> Dict[str, Dict[str, object]]:
    clean: Dict[str, Dict[str, object]] = {}
    for raw_id, raw in _clean_dict(value).items():
        if not isinstance(raw, dict):
            continue
        route_id = str(raw_id or raw.get("id", "")).strip()
        source = str(raw.get("source_town_key", "")).strip()
        destination = str(raw.get("destination_town_key", "")).strip()
        business_id = str(raw.get("business_id", "")).strip()
        if not route_id or not source or not destination or not business_id:
            continue
        clean[route_id] = {
            "id": route_id,
            "source_town_key": source,
            "destination_town_key": destination,
            "business_id": business_id,
            "good": str(raw.get("good", "General Goods")),
            "distance": max(1, int(raw.get("distance", 1))),
            "setup_cost": max(0, int(raw.get("setup_cost", 0))),
            "daily_income": max(0, int(raw.get("daily_income", 0))),
            "last_income_ordinal": max(0, int(raw.get("last_income_ordinal", 0))),
            "lifetime_income": max(0, int(raw.get("lifetime_income", 0))),
            "capacity_level": max(0, min(3, int(raw.get("capacity_level", 0)))),
            "escort_level": max(0, min(3, int(raw.get("escort_level", 0)))),
            "total_invested": max(0, int(raw.get("total_invested", 0))),
            "agreement_type": (
                str(raw.get("agreement_type", "Commercial Route"))
                if str(raw.get("agreement_type", "Commercial Route"))
                in {
                    "Commercial Route",
                    "Trade Charter",
                    "Mutual Aid",
                    "Cultural Exchange",
                }
                else "Commercial Route"
            ),
            "caravan_name": str(raw.get("caravan_name", "")),
            "caravan_last_ordinal": max(
                0,
                int(raw.get("caravan_last_ordinal", 0)),
            ),
            "caravan_deliveries": max(
                0,
                int(raw.get("caravan_deliveries", 0)),
            ),
            "caravan_sales_day": str(raw.get("caravan_sales_day", "")),
            "caravan_sales": {
                str(item): max(0, int(quantity))
                for item, quantity in _clean_dict(
                    raw.get("caravan_sales", {})
                ).items()
                if str(item or "").strip()
            },
            "caravan_journeys": max(
                0,
                int(raw.get("caravan_journeys", 0)),
            ),
            "caravan_last_journey_day": str(
                raw.get("caravan_last_journey_day", "")
            ),
            "active": bool(raw.get("active", True)),
        }
    return clean


def sanitize_civic_profile(value: object) -> Dict[str, object]:
    raw = _clean_dict(value)
    regional_contracts_raw = _clean_dict(raw.get("regional_contracts", {}))
    contracts: Dict[str, Dict[str, object]] = {}
    for raw_id, raw_contract in _clean_dict(
        regional_contracts_raw.get("contracts", {})
    ).items():
        if not isinstance(raw_contract, dict):
            continue
        contract_id = str(raw_id or raw_contract.get("id", "")).strip()
        contract_type = str(raw_contract.get("type", "")).strip()
        town_key = str(raw_contract.get("town_key", "")).strip()
        if not contract_id or contract_type not in {
            "supply",
            "public_works",
            "courier",
            "escort",
            "festival_trade",
        }:
            continue
        contracts[contract_id] = {
            "id": contract_id,
            "type": contract_type,
            "title": str(raw_contract.get("title", "Regional Contract")),
            "description": str(raw_contract.get("description", "")),
            "town_key": town_key,
            "route_id": str(raw_contract.get("route_id", "")),
            "item": str(raw_contract.get("item", "")),
            "quantity": max(0, int(raw_contract.get("quantity", 0))),
            "reward": max(0, int(raw_contract.get("reward", 0))),
            "reputation_reward": max(
                0,
                int(raw_contract.get("reputation_reward", 0)),
            ),
            "status": (
                str(raw_contract.get("status", "available"))
                if str(raw_contract.get("status", "available"))
                in {"available", "active", "completed"}
                else "available"
            ),
            "posted_key": str(raw_contract.get("posted_key", "")),
            "accepted_day": str(raw_contract.get("accepted_day", "")),
            "completed_day": str(raw_contract.get("completed_day", "")),
        }
    return {
        "campaign_endorsements": [
            str(entry)
            for entry in raw.get("campaign_endorsements", [])
            if str(entry or "").strip()
        ][-40:],
        "offices_held": [
            str(entry)
            for entry in raw.get("offices_held", [])
            if str(entry or "").strip()
        ][-20:],
        "elections_won": max(0, int(raw.get("elections_won", 0))),
        "elections_lost": max(0, int(raw.get("elections_lost", 0))),
        "votes_cast": max(0, int(raw.get("votes_cast", 0))),
        "lifetime_business_income": max(
            0,
            int(raw.get("lifetime_business_income", 0)),
        ),
        "lifetime_trade_income": max(
            0,
            int(raw.get("lifetime_trade_income", 0)),
        ),
        "lifetime_property_income": max(
            0,
            int(raw.get("lifetime_property_income", 0)),
        ),
        "regional_council": copy.deepcopy(
            raw.get("regional_council", {})
            if isinstance(raw.get("regional_council"), dict)
            else {}
        ),
        "regional_contracts": {
            "board_key": str(regional_contracts_raw.get("board_key", "")),
            "contracts": contracts,
            "completed_ids": [
                str(contract_id)
                for contract_id in regional_contracts_raw.get(
                    "completed_ids",
                    [],
                )
                if str(contract_id or "").strip()
            ][-80:],
            "journey_log": [
                str(line)
                for line in regional_contracts_raw.get("journey_log", [])
                if str(line or "").strip()
            ][-40:],
            "contracts_completed": max(
                0,
                int(regional_contracts_raw.get("contracts_completed", 0)),
            ),
        },
    }


__all__ = [
    "sanitize_civic_profile",
    "sanitize_player_businesses",
    "sanitize_player_properties",
    "sanitize_player_trade_routes",
]
