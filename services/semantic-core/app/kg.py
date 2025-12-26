from rdflib import Graph
from typing import Dict, Any, List

class SemanticDriverStore:
    def __init__(self, ttl_path: str):
        self.g = Graph()
        self.g.parse(ttl_path, format="turtle")

    def get_codec_name(self, model_uri: str) -> str:
        q = f"""
        PREFIX iot: <http://example.org/iot#>
        SELECT ?codecName WHERE {{
          <{model_uri}> iot:usesCodec ?codec .
          ?codec iot:codecName ?codecName .
        }} LIMIT 1
        """
        for row in self.g.query(q):
            return str(row.codecName)
        raise KeyError(f"No codec for model {model_uri}")

    def get_mappings(self, model_uri: str) -> List[Dict[str, Any]]:
        q = f"""
        PREFIX iot: <http://example.org/iot#>
        SELECT ?rawKey ?unifiedKey ?unit ?scale ?min ?max WHERE {{
          <{model_uri}> iot:hasFieldMapping ?m .
          ?m iot:rawKey ?rawKey ;
             iot:unifiedKey ?unifiedKey ;
             iot:unit ?unit ;
             iot:scale ?scale ;
             iot:min ?min ;
             iot:max ?max .
        }}
        """
        out = []
        for row in self.g.query(q):
            out.append({
                "rawKey": str(row.rawKey),
                "unifiedKey": str(row.unifiedKey),
                "unit": str(row.unit),
                "scale": float(row.scale),
                "min": float(row.min),
                "max": float(row.max),
            })
        return out
