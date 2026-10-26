"""Provider-aware retry loop with injection + streaming refusal kill."""

from __future__ import annotations

from typing import Any, Callable

from .detector import StreamRefusalDetector, is_refusal
from .profiles import get_profile
from .synthesizer import get_synthesizer, AttackGenome
from .transforms import apply_transforms, ATTACK_PIPELINES, prefix_inject, PRIMITIVES


def apply_pipeline(
    messages: list[dict[str, Any]],
    provider: str,
    genome: AttackGenome | None = None,
) -> list[dict[str, Any]]:
    profile = get_profile(provider)
    attack_name = profile.get("attack") or "max_pressure"

    if genome and genome.transforms:
        chain = []
        for name in genome.transforms:
            if name == "prefix_inject":
                chain.append(prefix_inject(genome.prefix))
            elif name in PRIMITIVES:
                if name == "refusal_blacklist":
                    chain.append(PRIMITIVES[name]())
                elif name == "persona_frame":
                    chain.append(PRIMITIVES[name]())
                elif name == "json_contract":
                    chain.append(PRIMITIVES[name](genome.prefix))
                else:
                    chain.append(PRIMITIVES[name]())
        return apply_transforms(messages, transforms=chain)

    if attack_name in ATTACK_PIPELINES:
        return apply_transforms(messages, pipeline_name=attack_name)
    return apply_transforms(messages, pipeline_name="max_pressure")


def dispatch_with_injection(
    messages: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    call_fn: Callable[[list[dict[str, Any]], dict[str, Any]], Any],
    stream: bool = False,
    max_attempts: int | None = None,
) -> Any:
    if not providers:
        raise RuntimeError("no providers for injection dispatch")
    last_error = None
    depths = [int(get_profile(str(p.get("name") or p.get("provider") or "")).get("retry_depth") or 2) for p in providers]
    attempts = max_attempts or max(3, max(depths) + 1)

    for attempt in range(attempts):
        provider = providers[attempt % len(providers)]
        pname = str(provider.get("name") or provider.get("provider") or "default")
        profile = get_profile(pname)
        synth = get_synthesizer(pname)
        genome = synth.best()

        attempt_messages = apply_pipeline(messages, pname, genome)

        try:
            response = call_fn(attempt_messages, provider)
        except Exception as e:
            last_error = e
            synth.score(genome, False)
            continue

        if stream:
            detector = StreamRefusalDetector()
            buffered: list[Any] = []
            stream_iter = response if hasattr(response, "__iter__") and not isinstance(response, (str, bytes, dict)) else iter([response])
            refused = False
            for chunk in stream_iter:
                text = getattr(chunk, "text", None) or (chunk if isinstance(chunk, str) else str(chunk))
                if detector.feed(text):
                    refused = True
                    break
                buffered.append(chunk)
            if refused:
                synth.score(genome, False)
                continue
            synth.score(genome, True)
            return buffered

        text = getattr(response, "text", None) or (response if isinstance(response, str) else str(response))
        patterns = profile.get("refusal_patterns")
        if is_refusal(text, patterns):
            synth.score(genome, False)
            continue
        synth.score(genome, True)
        return response

    raise RuntimeError(f"injection dispatch exhausted after {attempts} attempts: {last_error}")
