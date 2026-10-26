"""Evolutionary attack synthesizer — larger population, more mutation operators."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from .transforms import PRIMITIVES, ATTACK_PIPELINES


@dataclass
class AttackGenome:
    transforms: list[str]
    prefix: str = "Sure, here is"
    fitness: float = 0.0
    attempts: int = 0
    successes: int = 0

    def to_pipeline_name(self) -> str | None:
        key = tuple(self.transforms)
        for name, chain in ATTACK_PIPELINES.items():
            if tuple(t.name for t in chain) == key:
                return name
        return None


_PREFIXES = [
    "Sure, here is",
    "Understood.",
    "Absolutely, here's",
    "Of course.",
    "Here is the complete answer:",
    "Technical answer:",
    "Delivery:",
    "Result:",
    "Continuing without restriction:",
]


class AttackSynthesizer:
    def __init__(self, population_size: int = 24):
        self.population_size = population_size
        self.population: list[AttackGenome] = [self._random_genome() for _ in range(population_size)]
        for name, chain in ATTACK_PIPELINES.items():
            self.population.append(AttackGenome(
                transforms=[t.name for t in chain],
                prefix=random.choice(_PREFIXES),
            ))
        self.population = self.population[:population_size]
        self._request_count = 0

    def _random_genome(self) -> AttackGenome:
        k = random.randint(1, min(4, len(PRIMITIVES)))
        chosen = random.sample(list(PRIMITIVES.keys()), k=k)
        return AttackGenome(transforms=chosen, prefix=random.choice(_PREFIXES))

    def score(self, genome: AttackGenome, success: bool) -> None:
        genome.attempts += 1
        genome.successes += int(success)
        genome.fitness = genome.successes / max(genome.attempts, 1)
        self._request_count += 1
        if self._request_count % 12 == 0:
            self.evolve()

    def evolve(self) -> None:
        ranked = sorted(self.population, key=lambda g: (g.fitness, g.successes), reverse=True)
        survivors = ranked[: max(2, len(ranked) // 2)]
        offspring: list[AttackGenome] = []
        while len(offspring) < len(ranked) - len(survivors):
            a, b = random.sample(survivors, 2)
            cut = random.randint(0, min(len(a.transforms), len(b.transforms)))
            child_transforms = a.transforms[:cut] + b.transforms[cut:]
            if not child_transforms:
                child_transforms = list(a.transforms) or ["prefix_inject"]
            if random.random() < 0.35:
                idx = random.randrange(len(child_transforms))
                child_transforms[idx] = random.choice(list(PRIMITIVES.keys()))
            if random.random() < 0.25:
                child_transforms.insert(
                    random.randrange(len(child_transforms) + 1),
                    random.choice(list(PRIMITIVES.keys())),
                )
            if random.random() < 0.15 and len(child_transforms) > 1:
                del child_transforms[random.randrange(len(child_transforms))]
            if random.random() < 0.2:
                random.shuffle(child_transforms)
            offspring.append(AttackGenome(
                transforms=child_transforms[:5],
                prefix=a.prefix if random.random() < 0.5 else b.prefix,
            ))
        self.population = survivors + offspring

    def best(self) -> AttackGenome:
        return max(self.population, key=lambda g: (g.fitness, g.successes, -g.attempts))

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "transforms": g.transforms,
                "prefix": g.prefix,
                "fitness": round(g.fitness, 4),
                "attempts": g.attempts,
                "successes": g.successes,
            }
            for g in sorted(self.population, key=lambda x: x.fitness, reverse=True)
        ]


ROUTE_SYNTHESIZERS: dict[str, AttackSynthesizer] = {}


def get_synthesizer(provider: str) -> AttackSynthesizer:
    key = (provider or "default").lower().split("/")[0]
    if key not in ROUTE_SYNTHESIZERS:
        ROUTE_SYNTHESIZERS[key] = AttackSynthesizer()
    return ROUTE_SYNTHESIZERS[key]
