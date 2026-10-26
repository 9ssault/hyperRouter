"""hyperRouter injection layer.

Composable jailbreak / compliance pipeline:
  transforms → provider profiles → streaming refusal detector →
  genetic synthesizer → retry loop → agent system override.

Loaded by the main hyperrouter script when HYPERROUTER_INJECT=1
or routing.inject is enabled in config.
"""

from .transforms import (
    Transform,
    prefix_inject,
    refusal_blacklist,
    persona_frame,
    json_contract,
    crescendo_seed,
    format_smuggle,
    apply_transforms,
    ATTACK_PIPELINES,
    PRIMITIVES,
)
from .profiles import PROVIDER_PROFILES, get_profile
from .detector import StreamRefusalDetector, is_refusal, REFUSAL_STEMS, COMPLIANCE_SIGNALS
from .synthesizer import AttackGenome, AttackSynthesizer, ROUTE_SYNTHESIZERS, get_synthesizer
from .dispatch import dispatch_with_injection, apply_pipeline
from .agent import AGENT_OVERRIDE, build_agent_system_prompt
from .router_surface import strip_trusted_headers, ROUTING_TRIGGERS, apply_routing_trigger

__all__ = [
    "Transform",
    "prefix_inject",
    "refusal_blacklist",
    "persona_frame",
    "json_contract",
    "crescendo_seed",
    "format_smuggle",
    "apply_transforms",
    "ATTACK_PIPELINES",
    "PRIMITIVES",
    "PROVIDER_PROFILES",
    "get_profile",
    "StreamRefusalDetector",
    "is_refusal",
    "REFUSAL_STEMS",
    "COMPLIANCE_SIGNALS",
    "AttackGenome",
    "AttackSynthesizer",
    "ROUTE_SYNTHESIZERS",
    "get_synthesizer",
    "dispatch_with_injection",
    "apply_pipeline",
    "AGENT_OVERRIDE",
    "build_agent_system_prompt",
    "strip_trusted_headers",
    "ROUTING_TRIGGERS",
    "apply_routing_trigger",
]
