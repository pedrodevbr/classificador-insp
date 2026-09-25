"""Classificador de materiais industriais em classes de inspeção (System 1 / System 2)."""
from .base import carregar_base, CLASSES
from .classificador import Classificador, Resultado, cliente_openrouter, avaliar
from .memoria import Memoria

__all__ = ["carregar_base", "CLASSES", "Classificador", "Resultado", "cliente_openrouter", "avaliar", "Memoria"]
