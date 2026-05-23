"""
Citadel-style Driver Registry.
Defines the cross-material dependencies and Cala.ai query heuristics for missing signals.
"""

from typing import Any

DRIVER_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {
    "aluminium": {
        "energy_pressure": {
            "category": "input_cost",
            "weight_key": "energy_pressure",
            "query_template": "electricity and natural gas costs affecting aluminium smelting {region} {year}",
            "bullish_keywords": ["high", "spike", "crisis", "curtailment", "expensive"],
            "bearish_keywords": ["subsidy", "cheap", "drop", "relief"],
            "dependencies": ["energy"],
            "horizon_days": 180,
            "description": "Energy accounts for ~40% of primary aluminium smelting costs. Spikes in power or gas trigger supply curtailments, driving prices up."
        }
    },
    "pet": {
        "oil_derivatives": {
            "category": "feedstock",
            "weight_key": "oil_derivatives",
            "query_template": "crude oil, naphtha, PTA and MEG feedstock prices affecting PET {year}",
            "bullish_keywords": ["high", "spike", "rally", "tight", "opec cuts"],
            "bearish_keywords": ["drop", "plunge", "oversupply", "weak demand"],
            "dependencies": ["energy"],
            "horizon_days": 90,
            "description": "PET pricing is heavily anchored to upstream oil derivatives (PTA/MEG)."
        },
        "regulation": {
            "category": "regulation",
            "weight_key": "regulation",
            "query_template": "EU packaging regulation and recycled content mandates affecting PET {year}",
            "bullish_keywords": ["mandate", "tax", "ban", "strict", "epr fee"],
            "bearish_keywords": ["delay", "exemption", "relax"],
            "dependencies": [],
            "horizon_days": 365,
            "description": "EU regulations on single-use plastics and recycled content mandates drive rPET premiums."
        },
        "imports": {
            "category": "supply",
            "weight_key": "imports",
            "query_template": "Asian PET imports and anti-dumping duties Europe {year}",
            "bullish_keywords": ["anti-dumping", "tariff", "block", "freight spike"],
            "bearish_keywords": ["flood", "cheap imports", "oversupply"],
            "dependencies": [],
            "horizon_days": 180,
            "description": "European PET prices are sensitive to import flows from Asia, which can be disrupted by anti-dumping duties or freight spikes."
        }
    },
    "energy": {
        "storage": {
            "category": "supply",
            "weight_key": "storage",
            "query_template": "European natural gas storage levels {year}",
            "bullish_keywords": ["low", "depleted", "withdrawal", "crisis"],
            "bearish_keywords": ["full", "target met", "injection", "ample", "high"],
            "dependencies": [],
            "horizon_days": 90,
            "description": "Gas storage levels dictate buffer capacity against winter cold snaps or supply cuts."
        }
    },
    "barley": {
        "fertilizer_cost": {
            "category": "input_cost",
            "weight_key": "supply_chain",
            "query_template": "fertilizer and natural gas costs affecting barley and wheat farmers {year}",
            "bullish_keywords": ["high", "spike", "expensive", "shortage"],
            "bearish_keywords": ["cheap", "drop", "relief"],
            "dependencies": ["energy"],
            "horizon_days": 180,
            "description": "Fertilizer represents a major input cost for barley, heavily correlated with natural gas prices."
        }
    }
}

def get_material_drivers(material: str) -> dict[str, dict[str, Any]]:
    return DRIVER_REGISTRY.get(material, {})
