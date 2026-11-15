import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MEMORY_FILE = Path(__file__).resolve().parent / "agent_memory.json"


class MemoryManager:
    def __init__(self):
        self._skills: dict[str, dict] = {}
        self._facts: dict[str, int] = {}
        self._task_history: list[dict] = []
        self._lessons: list[str] = []
        self._load()

    def _load(self) -> None:
        if _MEMORY_FILE.exists():
            try:
                data = json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
                self._skills = data.get("skills", {})
                self._facts = data.get("facts", {})
                self._task_history = data.get("task_history", [])
                self._lessons = data.get("lessons", [])
                logger.info(f"Loaded memory: {len(self._skills)} skills, {len(self._facts)} facts, {len(self._task_history)} tasks, {len(self._lessons)} lessons")
            except Exception:
                logger.warning("Failed to load memory file, starting fresh")

    def _save(self) -> None:
        data = {
            "skills": self._skills,
            "facts": self._facts,
            "task_history": self._task_history,
            "lessons": self._lessons,
        }
        _MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def record_task_trajectory(
        self,
        task: str,
        success: bool,
        iterations: int,
        trajectory: list[dict],
    ) -> None:
        """
        trajectory: list of {reasoning, tool_name, tool_args, observation_summary}
        """
        phases = self._extract_phases(trajectory)

        record = {
            "task": task,
            "success": success,
            "iterations": iterations,
            "phases": phases,
        }
        self._task_history.append(record)
        if len(self._task_history) > 30:
            self._task_history = self._task_history[-30:]

        if success:
            self._record_skill_from_phases(task, phases)
            self._extract_lessons(trajectory)

        self._save()

    def _extract_phases(self, trajectory: list[dict]) -> list[dict]:
        phases = []
        current_phase = {"name": "unknown", "summary": [], "tools_used": set()}

        for step in trajectory:
            tool = step.get("tool_name", "")
            obs = step.get("observation", "")[:200]
            reasoning = step.get("reasoning", "")

            phase_name = self._classify_step(tool, obs, reasoning)

            if phase_name != current_phase["name"]:
                if current_phase["summary"]:
                    phases.append({
                        "name": current_phase["name"],
                        "summary": "; ".join(current_phase["summary"][-5:]),
                        "tools": list(current_phase["tools_used"]),
                    })
                current_phase = {"name": phase_name, "summary": [], "tools_used": set()}

            summary_line = self._summarize_step(tool, obs, reasoning)
            if summary_line:
                current_phase["summary"].append(summary_line)
            current_phase["tools_used"].add(tool)

        if current_phase["summary"]:
            phases.append({
                "name": current_phase["name"],
                "summary": "; ".join(current_phase["summary"][-5:]),
                "tools": list(current_phase["tools_used"]),
            })

        return phases

    def _classify_step(self, tool: str, obs: str, reasoning: str) -> str:
        context = (reasoning + " " + obs).lower()
        if tool in ("find_block", "collect_block", "pickup_item"):
            return "gathering"
        if tool in ("craft_item", "check_crafting_recipe"):
            return "crafting"
        if tool in ("place_block",):
            if "crafting_table" in context:
                return "crafting"
            if "furnace" in context:
                return "furnace_placement"
            return "building"
        if tool in ("move_to_interactable_block",):
            if "furnace" in context:
                return "furnace_interaction"
            if "crafting_table" in context:
                return "crafting"
            if "chest" in context:
                return "chest_interaction"
            return "movement"
        if tool in ("interact_with_furnace", "check_furnace"):
            if "take_result" in obs or "take_result" in context:
                return "taking_result"
            if "put_item" in obs or "put_fuel" in obs or "put_fuel" in context or "put_item" in context:
                return "furnace_interaction"
            return "waiting_smelting"
        if tool in ("interact_with_chest", "check_chest_contents"):
            return "chest_interaction"
        if tool in ("move",):
            return "movement"
        if tool == "check_inventory":
            return "inventory_check"
        if tool == "find_block":
            return "searching"
        return "other"

    def _summarize_step(self, tool: str, obs: str, reasoning: str) -> str | None:
        if "Collected block" in obs:
            block = obs.split("'")[1] if "'" in obs else "block"
            return f"mined {block}"
        if "Crafted" in obs:
            parts = obs.split("Crafted ")[1].split(" ")[0] if "Crafted " in obs else "item"
            return f"crafted {parts}"
        if "Placed" in obs:
            block = obs.split("'")[1] if "'" in obs else "block"
            return f"placed {block}"
        if "Reached interaction range" in obs:
            return "moved to interaction range"
        if "Reached" in obs and "within" in obs:
            return "moved to target"
        if "put_item" in obs and "ok" in obs:
            return "loaded furnace input"
        if "put_fuel" in obs and "ok" in obs:
            return "loaded furnace fuel"
        if "take_result" in obs and "ok" in obs:
            return "took smelted result"
        if "deposit" in obs and "ok" in obs:
            return "deposited item into chest"
        if tool == "check_furnace":
            if "Status: smelting" in obs:
                return "checking smelting progress"
            if "Output:" in obs and ("iron_ingot" in obs or "cooked" in obs):
                return "smelting complete"
            if "Status: no fuel" in obs:
                return "fuel ran out"
            return "checking furnace"
        if tool == "find_block":
            block = obs.split("Block: ")[1].split("\n")[0].strip() if "Block: " in obs else None
            if block:
                return f"found {block}"
            return None
        if tool == "check_inventory":
            return None
        if tool == "position":
            return None
        if "No harvestable tool" in obs:
            return "need better tool"
        if "cannot place" in obs.lower() or "Failed to place" in obs:
            return "placement blocked by terrain"
        if "wedged" in obs or "escape" in obs or "abort" in obs.lower():
            return None
        return None

    def _record_skill_from_phases(self, task: str, phases: list[dict]) -> None:
        skill_name = self._task_to_skill_name(task)
        if not skill_name:
            return

        steps: list[str] = []
        seen_steps: set[str] = set()
        for phase in phases:
            summary = phase["summary"]
            if summary:
                parts = [s.strip() for s in summary.split("; ") if s.strip()]
                for p in parts:
                    if p not in seen_steps and "blocked" not in p and "cannot" not in p:
                        seen_steps.add(p)
                        steps.append(p)

        if len(steps) < 2:
            return

        existing = self._skills.get(skill_name, {})
        count = existing.get("count", 0) + 1

        if count >= 2 and skill_name in self._skills:
            merged = []
            old_steps = {s.strip() for s in existing.get("steps", [])}
            new_steps = set(steps)
            common = old_steps & new_steps
            merged = [s for s in steps if s in common]
            if not merged:
                merged = list(new_steps | old_steps)
            steps = merged[:8]

        self._skills[skill_name] = {
            "description": self._skill_description(skill_name),
            "steps": steps,
            "count": count,
        }

    def _task_to_skill_name(self, task: str) -> str | None:
        t = task.lower()
        if any(kw in t for kw in ["cook", "steak", "beef", "porkchop", "mutton", "chicken"]):
            return "cook_with_furnace"
        if any(kw in t for kw in ["smelt", "iron", "copper", "gold", "ingot", "ore"]):
            return "smelt_ore"
        if any(kw in t for kw in ["build", "construct", "house", "wall", "tower", "church", "pyramid"]):
            return "build_structure"
        if any(kw in t for kw in ["chat", "talk", "say", "greet", "hello"]):
            return "chat"
        if any(kw in t for kw in ["farm", "plant", "harvest", "crop", "seed"]):
            return "farming"
        if any(kw in t for kw in ["mine", "dig", "tunnel"]):
            return "mining"
        if any(kw in t for kw in ["collect", "gather", "collect wood", "gather wood"]):
            return "gathering"
        if any(kw in t for kw in ["craft", "make", "create"]):
            return "crafting"
        # Generic: any task with enough steps gets recorded as "task_skill"
        return "general_task"

    def _skill_description(self, name: str) -> str:
        return {
            "cook_with_furnace": "How to cook raw meat into food using a furnace",
            "smelt_ore": "How to mine and smelt ore into an ingot",
            "build_structure": "How to build structures",
            "chat": "How to chat and respond to messages",
            "farming": "How to farm and harvest crops",
            "mining": "How to mine blocks",
            "gathering": "How to gather resources",
            "crafting": "How to craft items",
            "general_task": "How to accomplish general tasks",
        }.get(name, f"How to accomplish: {name}")

    def _extract_lessons(self, trajectory: list[dict]) -> None:
        consecutive_placement_failures = 0
        fuel_ran_out = False
        fuel_added_count = 0
        used_recycle = False
        found_prebuilt = False

        for step in trajectory:
            obs = step.get("observation", "")
            tool = step.get("tool_name", "")

            if "cannot place" in obs.lower() or "Failed to place" in obs:
                consecutive_placement_failures += 1
            elif "Placed" in obs:
                consecutive_placement_failures = 0

            if "fuel ran out" in obs or "no fuel" in obs.lower():
                fuel_ran_out = True
            if "put_fuel" in obs and "ok" in obs:
                fuel_added_count += 1

            if tool == "collect_block" and ("crafting_table" in obs or "furnace" in obs):
                used_recycle = True

            if tool == "check_furnace" and "Output: iron_ingot" in obs and "Input: empty" in obs:
                found_prebuilt = True

        if consecutive_placement_failures >= 3:
            self._add_lesson("Place blocks on flat ground (dirt/stone at feet level), not on hillsides or against air")

        if fuel_ran_out and fuel_added_count > 0:
            self._add_lesson("ALWAYS add 2+ fuel items at once — 1 plank is rarely enough to fully smelt one item")

        if used_recycle:
            self._add_lesson("After using crafting_table or furnace, pick it up with collect_block to reuse nearby")

        if found_prebuilt:
            self._add_lesson("Check nearby furnaces first — they may already have smelted items in output slot")

    def _add_lesson(self, lesson: str) -> None:
        if lesson not in self._lessons:
            self._lessons.append(lesson)
            logger.info(f"Learned lesson: {lesson}")

    def add_fact(self, fact: str) -> None:
        self._facts[fact] = self._facts.get(fact, 0) + 1

    def learn_from_iteration(
        self, tool_name: str, observation: str, reasoning: str
    ) -> None:
        if "Collected block 'iron_ore'" in observation:
            self.add_fact("stone_pickaxe can mine iron_ore → raw_iron")
        if "beef smelted" in observation.lower() or ("cooked_beef" in observation and "Output" in observation):
            self.add_fact("beef + fuel in furnace → cooked_beef (steak)")
        if "raw_iron smelted" in observation.lower() or ("iron_ingot" in observation and "Output" in observation):
            self.add_fact("raw_iron + fuel in furnace → iron_ingot")
        if "interact_with_chest" in tool_name and "ok" in observation.lower():
            self.add_fact("use interact_with_chest deposit to store items")
        if "collected block 'crafting_table'" in observation.lower():
            self.add_fact("crafting_table can be picked up with collect_block after use")
        if "collected block 'furnace'" in observation.lower():
            self.add_fact("furnace can be picked up with collect_block after use")

    def get_relevant_memories(self, task: str) -> str:
        parts: list[str] = []
        keywords = task.lower().split()

        skill_name = self._task_to_skill_name(task)
        if skill_name and skill_name in self._skills:
            sk = self._skills[skill_name]
            parts.append(f"## How to {sk['description']} (learned from {sk['count']} past successes)")
            for i, step in enumerate(sk["steps"], 1):
                parts.append(f"  {i}. {step}")

        if self._lessons:
            parts.append("\n## CRITICAL Lessons Learned")
            for lesson in self._lessons[:8]:
                parts.append(f"  - {lesson}")

        relevant_facts = [
            f for f in self._facts if any(kw in f.lower() for kw in keywords)
        ][:8]
        if relevant_facts:
            parts.append("\n## Key Facts (from past experience)")
            for fact in relevant_facts:
                parts.append(f"  - {fact}")

        if not parts:
            return ""

        return "\n".join(parts)
