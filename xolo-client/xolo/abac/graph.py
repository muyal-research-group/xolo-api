import networkx as nx
from xolo.abac.models import Event, Policy
from typing import List
from collections import Counter
import numpy as np
from pathlib import Path
import os


class GraphBuilder:

    def __init__(self):
        self.graph = None

    def event_similarity(self, e1: Event, e2: Event, weights: dict) -> float:
        """
        Calcula la similitud entre dos eventos basada en la suma
        de los pesos de los atributos coincidentes.
        """
        score = 0.0
        if e1.subject.value.strip().lower() == e2.subject.value.strip().lower():
            score += weights.get("rol", 0)
        if e1.asset.value.strip().lower() == e2.asset.value.strip().lower():
            score += weights.get("recurso", 0)
        if e1.space.value.strip().lower() == e2.space.value.strip().lower():
            score += weights.get("ubicacion", 0)
        if e1.time.value.strip().lower() == e2.time.value.strip().lower():
            score += weights.get("rango_horario", 0)
        if e1.action.value.strip().lower() == e2.action.value.strip().lower():
            score += weights.get("accion", 0)
        return score

    def build_event_graph(self, policies: List[Policy], similarity_threshold: float = 0.3) -> nx.Graph:
        """
        Construye un grafo de eventos, conectando solo eventos cuya
        similitud supere un umbral especificado.
        Al finalizar, exporta automáticamente el grafo en formato .gexf (para Gephi).
        """
        G = nx.Graph()
        attribute_weights = self.calculate_attribute_weights(policies)

        # Crear nodos con atributos útiles para Gephi
        for policy in policies:
            for event in policy.events:
                G.add_node(
                    event.event_id,
                    policy_id=policy.policy_id,
                    rol=str(event.subject.value) if event.subject.value else "NA",
                    recurso=str(event.asset.value) if event.asset.value else "NA",
                    ubicacion=str(event.space.value) if event.space.value else "NA",
                    rango_horario=str(event.time.value) if event.time.value else "NA",
                    accion=str(event.action.value) if event.action.value else "NA",
                )

        event_ids = list(G.nodes)

        # Crear aristas según la similitud ponderada
        for i in range(len(event_ids)):
            for j in range(i + 1, len(event_ids)):
                e1_id, e2_id = event_ids[i], event_ids[j]
                e1 = None
                e2 = None

                # Recuperar los eventos correspondientes
                for p in policies:
                    for ev in p.events:
                        if ev.event_id == e1_id:
                            e1 = ev
                        elif ev.event_id == e2_id:
                            e2 = ev
                    if e1 and e2:
                        break

                if not e1 or not e2:
                    continue

                sim = self.event_similarity(e1, e2, attribute_weights)
                if sim >= similarity_threshold:
                    G.add_edge(e1.event_id, e2.event_id, weight=float(sim))

        self.graph = G

        # === Limpieza antes de exportar ===
        for n, attrs in G.nodes(data=True):
            for k, v in list(attrs.items()):
                if v is None or v == "" or (isinstance(v, float) and np.isnan(v)):
                    G.nodes[n][k] = "NA"

        for u, v, attrs in G.edges(data=True):
            for k, val in list(attrs.items()):
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    G.edges[u, v][k] = 0.0

        # === Exportación automática ===
        output_dir = "exports"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "event_graph.gexf")

        try:
            nx.write_gexf(G, output_path, encoding="utf-8")
            print(f"[GraphBuilder] Grafo exportado automáticamente a: {output_path}")
        except Exception as e:
            print(f"[GraphBuilder] Error al exportar el grafo automáticamente: {e}")

        return self.graph

    @staticmethod
    def calculate_attribute_weights(policies: list[Policy]) -> dict:
        """
        Calcula pesos dinámicos para los atributos basado en su entropía (diversidad) en las políticas.
        """
        attribute_values = {
            "rol": [],
            "recurso": [],
            "ubicacion": [],
            "rango_horario": [],
            "accion": []
        }

        for policy in policies:
            for event in policy.events:
                attribute_values["rol"].append(event.subject.value)
                attribute_values["recurso"].append(event.asset.value)
                attribute_values["ubicacion"].append(event.space.value)
                attribute_values["rango_horario"].append(event.time.value)
                attribute_values["accion"].append(event.action.value)

        entropies = {}
        for attribute, values in attribute_values.items():
            if not values:
                entropies[attribute] = 0
                continue

            counts = Counter(values)
            probabilities = [freq / len(values) for freq in counts.values()]
            entropy = -sum(p * np.log2(p) for p in probabilities if p > 0)
            entropies[attribute] = entropy

        total_entropy = sum(entropies.values()) or 1  # Evitar división entre cero
        weights = {attr: entropies[attr] / total_entropy for attr in entropies}

        return weights

    def export_graph(self, output_path: str, format: str = "gexf") -> None:
        """
        Exporta el grafo construido a un archivo compatible con Gephi.
        :param output_path: Ruta destino del archivo (por ejemplo, 'output/policies.gexf').
        :param format: Formato de exportación ('gexf' o 'graphml').
        """
        if self.graph is None:
            raise ValueError("No hay grafo construido. Ejecuta build_event_graph primero.")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Limpieza antes de exportar
        for n, attrs in self.graph.nodes(data=True):
            for k, v in list(attrs.items()):
                if v is None or v == "" or (isinstance(v, float) and np.isnan(v)):
                    self.graph.nodes[n][k] = "NA"

        for u, v, attrs in self.graph.edges(data=True):
            for k, val in list(attrs.items()):
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    self.graph.edges[u, v][k] = 0.0

        # Exportación
        if format == "gexf":
            nx.write_gexf(self.graph, output_path, encoding="utf-8")
        elif format == "graphml":
            nx.write_graphml(self.graph, output_path)
        else:
            raise ValueError("Formato no soportado. Usa 'gexf' o 'graphml'.")

        print(f"[GraphBuilder] Grafo exportado manualmente a: {output_path}")
