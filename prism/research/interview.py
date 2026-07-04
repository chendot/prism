"""STORM-style interview placeholder for Layer 1."""

from __future__ import annotations

from prism.core.models import Ontology
from prism.research.perspectives import perspectives_for


def generate_questions(topic: str, ontology: Ontology) -> list[dict[str, str]]:
    """Generate placeholder perspective-driven questions for a topic."""

    questions = []
    for perspective in perspectives_for(ontology):
        name = perspective.get("name", "未命名视角")
        focus = perspective.get("focus", "")
        questions.append(
            {
                "perspective": name,
                "question": f"从{name}看，{topic}中与{focus}相关的关键实体和关系是什么？",
            }
        )
    return questions
