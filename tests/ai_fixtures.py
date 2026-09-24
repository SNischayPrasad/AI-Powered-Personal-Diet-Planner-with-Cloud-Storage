"""Test doubles and fixtures for the AI planner.

``ScriptedProvider`` stands in for a real LLM API: it records what it was asked and returns a
canned answer (or raises a canned error). The canned answers are hand-written meal plans whose
numbers are internally consistent (4·protein + 4·carbs + 9·fat ≈ calories).
"""

import copy
import json

from ai_engine.nutrition import PlanRequest
from ai_engine.options import ActivityLevel, Cuisine, DietaryPreference, Goal, Sex


class ScriptedProvider:
    name = "scripted"
    model = "scripted-model-1"

    def __init__(self, reply):
        self.reply = reply
        self.calls: list[dict] = []

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict) -> str:
        self.calls.append({"system": system_prompt, "user": user_prompt, "schema": schema})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def reference_request(**overrides) -> PlanRequest:
    """Female, 28 y, 165 cm, 60 kg, moderately active, vegetarian, balanced → 2,060 kcal."""
    values = {
        "age": 28,
        "sex": Sex.FEMALE,
        "height_cm": 165,
        "weight_kg": 60,
        "activity_level": ActivityLevel.MODERATELY_ACTIVE,
        "dietary_preference": DietaryPreference.VEGETARIAN,
        "goal": Goal.BALANCED,
        "allergies": frozenset(),
        "cuisine": Cuisine.ANY,
    }
    values.update(overrides)
    return PlanRequest(**values)


VALID_AI_PLAN = {
    "breakfast": {
        "name": "Besan Chilla with Mint Chutney",
        "description": "Savoury gram-flour pancakes with onion and tomato.",
        "portion": "3 chillas",
        "ingredients": ["gram flour", "onion", "tomato", "coriander", "mint chutney"],
        "calories": 500, "protein_g": 20, "carbs_g": 70, "fat_g": 16, "fiber_g": 9,
        "why": "Protein from gram flour keeps you full through the morning.",
    },
    "lunch": {
        "name": "Rajma Rice Bowl",
        "description": "Kidney bean curry with steamed rice and cucumber.",
        "portion": "1 bowl rajma + 1 cup rice",
        "ingredients": ["kidney beans", "rice", "onion", "tomato", "cucumber"],
        "calories": 720, "protein_g": 28, "carbs_g": 100, "fat_g": 22, "fiber_g": 14,
        "why": "Beans and rice together give a complete, filling lunch.",
    },
    "snack": {
        "name": "Fruit Chaat",
        "description": "Seasonal fruit with lemon and chaat masala.",
        "portion": "1 bowl",
        "ingredients": ["apple", "papaya", "guava", "lemon", "chaat masala"],
        "calories": 210, "protein_g": 8, "carbs_g": 30, "fat_g": 6, "fiber_g": 6,
        "why": "Light and refreshing between meals.",
    },
    "dinner": {
        "name": "Paneer Bhurji with Roti",
        "description": "Crumbled paneer with vegetables and whole-wheat rotis.",
        "portion": "1 bowl bhurji + 2 rotis",
        "ingredients": ["paneer", "onion", "tomato", "bell pepper", "whole-wheat flour"],
        "calories": 630, "protein_g": 26, "carbs_g": 85, "fat_g": 22, "fiber_g": 8,
        "why": "Paneer adds protein to an easy home-style dinner.",
    },
    "tips": ["Eat slowly and enjoy your meals.", "Add a side salad when you can."],
}


def ai_plan(**meal_changes) -> dict:
    """A deep copy of VALID_AI_PLAN with per-meal field changes, e.g.
    ai_plan(dinner={"name": "Chicken Curry"})."""
    plan = copy.deepcopy(VALID_AI_PLAN)
    for slot, changes in meal_changes.items():
        plan[slot].update(changes)
    return plan


def as_json(plan: dict) -> str:
    return json.dumps(plan)
