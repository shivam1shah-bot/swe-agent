"""
Parser for Mermaid diagrams.
"""

import re
from typing import Dict, Any, List, Tuple
from src.services.agents_catalogue.genspec.src.parsers.base_parser import BaseParser


class MermaidParser(BaseParser):
    """
    Parser for Mermaid diagrams.
    """
    
    def __init__(self):
        """
        Initialize the Mermaid parser.
        """
        # Regex patterns for different diagram types
        self.patterns = {
            "flowchart": r"flowchart\s+[A-Za-z0-9]+",
            "sequenceDiagram": r"sequenceDiagram",
            "classDiagram": r"classDiagram",
            "stateDiagram": r"stateDiagram(-v2)?",
            "entityRelationshipDiagram": r"erDiagram",
            "gantt": r"gantt",
            "pie": r"pie",
            "graph": r"graph\s+[A-Za-z0-9]+",
        }
        
        # Regex for node definitions and connections
        self.node_pattern = r"([A-Za-z0-9_-]+)(\[\"[^\"]*\"\]|\[[^\]]*\]|\(\([^\)]*\)\)|\([^\)]*\)|{[^}]*}|>\"[^\"]*\"|>\"[^\"]*\")"
        self.connection_pattern = r"([A-Za-z0-9_-]+)\s*(-[-.]+>|--[-.]+|==+>|==+|--+|-.+-)(?:\|([^|]+)\|)?\s*([A-Za-z0-9_-]+)"
    
    def validate(self, content: str) -> bool:
        """
        Validate if the content is a Mermaid diagram.
        
        Args:
            content: The content to validate
            
        Returns:
            True if the content is a Mermaid diagram, False otherwise
        """
        # Check if content contains any Mermaid diagram type

        content = content.strip()
        for pattern in self.patterns.values():
            print("Validating content in Mermaid Parser", pattern, content)
            if re.search(pattern, content, re.MULTILINE):
                return True
        return False
    
    def parse(self, content: str, **kwargs) -> Dict[str, Any]:
        """
        Parse a Mermaid diagram and extract components and relationships.
        
        Args:
            content: The Mermaid diagram content
            **kwargs: Additional parser-specific arguments
            
        Returns:
            Dictionary containing the parsed diagram data
        """
        diagram_type = self._get_diagram_type(content)
        
        if not diagram_type:
            return {"error": "Unknown diagram type"}
        
        # Extract nodes and connections based on diagram type
        if diagram_type in ["flowchart", "graph"]:
            nodes = self._extract_nodes(content)
            connections = self._extract_connections(content)
        elif diagram_type == "classDiagram":
            nodes = self._extract_classes(content)
            connections = self._extract_class_relationships(content)
        elif diagram_type == "erDiagram":
            nodes = self._extract_entities(content)
            connections = self._extract_er_relationships(content)
        else:
            # For other diagram types, provide basic extraction
            nodes = []
            connections = []
        
        return {
            "diagram_type": diagram_type,
            "content": content,
            "components": nodes,
            "relationships": connections
        }
    
    def _get_diagram_type(self, content: str) -> str:
        """
        Determine the type of Mermaid diagram.
        
        Args:
            content: The Mermaid diagram content
            
        Returns:
            The diagram type or empty string if unknown
        """
        for diagram_type, pattern in self.patterns.items():
            if re.search(pattern, content, re.MULTILINE):
                return diagram_type
        return ""
    
    def _extract_nodes(self, content: str) -> List[Dict[str, str]]:
        """
        Extract nodes from a flowchart or graph diagram.
        
        Args:
            content: The diagram content
            
        Returns:
            List of node dictionaries
        """
        nodes = []
        matches = re.finditer(self.node_pattern, content)
        
        for match in matches:
            node_id = match.group(1)
            label_match = re.search(r'\["([^"]+)"\]|\[([^\]]+)\]', match.group(2))
            
            if label_match:
                label = label_match.group(1) if label_match.group(1) else label_match.group(2)
            else:
                label = node_id
            
            nodes.append({
                "id": node_id,
                "label": label,
                "type": self._determine_node_type(match.group(2))
            })
        
        return nodes
    
    def _determine_node_type(self, node_def: str) -> str:
        """
        Determine the type of node based on its definition.
        
        Args:
            node_def: The node definition string
            
        Returns:
            The node type
        """
        if "(" in node_def and ")" in node_def:
            if "((" in node_def and "))" in node_def:
                return "circle"
            return "round"
        elif "[" in node_def and "]" in node_def:
            return "box"
        elif "{" in node_def and "}" in node_def:
            return "rhombus"
        elif ">" in node_def:
            return "flag"
        return "default"
    
    def _extract_connections(self, content: str) -> List[Dict[str, str]]:
        """
        Extract connections from a flowchart or graph diagram.
        
        Args:
            content: The diagram content
            
        Returns:
            List of connection dictionaries
        """
        connections = []
        matches = re.finditer(self.connection_pattern, content)
        
        for match in matches:
            source = match.group(1)
            connection_type = match.group(2)
            label = match.group(3) if match.group(3) else ""
            target = match.group(4)
            
            connections.append({
                "source": source,
                "target": target,
                "label": label,
                "type": self._determine_connection_type(connection_type)
            })
        
        return connections
    
    def _determine_connection_type(self, conn_def: str) -> str:
        """
        Determine the type of connection based on its definition.
        
        Args:
            conn_def: The connection definition string
            
        Returns:
            The connection type
        """
        if "-->" in conn_def or "->-" in conn_def or "-.->" in conn_def:
            return "arrow"
        elif "==>" in conn_def or "==" in conn_def:
            return "thick"
        elif "--" in conn_def:
            return "line"
        elif "-.-" in conn_def:
            return "dotted"
        return "default"
    
    def _extract_classes(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract classes from a class diagram.
        
        Args:
            content: The diagram content
            
        Returns:
            List of class dictionaries
        """
        classes = []
        class_pattern = r"class\s+([A-Za-z0-9_-]+)\s*{([^}]*)}"
        
        for match in re.finditer(class_pattern, content, re.DOTALL):
            class_name = match.group(1)
            class_body = match.group(2) if match.group(2) else ""
            
            methods = []
            attributes = []
            
            for line in class_body.split("\n"):
                line = line.strip()
                if "(" in line and ")" in line:  # Likely a method
                    methods.append(line)
                elif line:  # Likely an attribute
                    attributes.append(line)
            
            classes.append({
                "id": class_name,
                "name": class_name,
                "attributes": attributes,
                "methods": methods
            })
        
        return classes
    
    def _extract_class_relationships(self, content: str) -> List[Dict[str, str]]:
        """
        Extract relationships from a class diagram.
        
        Args:
            content: The diagram content
            
        Returns:
            List of relationship dictionaries
        """
        relationships = []
        relationship_pattern = r"([A-Za-z0-9_-]+)\s*(--|<\|--|o--|<--|\.\.|<\.\.|o\.\.|<\.\.)\s*([A-Za-z0-9_-]+)\s*:?\s*([^:\n]*)"
        
        for match in re.finditer(relationship_pattern, content):
            source = match.group(1)
            relationship_type = match.group(2)
            target = match.group(3)
            label = match.group(4).strip() if match.group(4) else ""
            
            relationships.append({
                "source": source,
                "target": target,
                "label": label,
                "type": self._determine_class_relationship_type(relationship_type)
            })
        
        return relationships
    
    def _determine_class_relationship_type(self, rel_type: str) -> str:
        """
        Determine the type of class relationship.
        
        Args:
            rel_type: The relationship type string
            
        Returns:
            The relationship type
        """
        if "<|--" in rel_type:
            return "inheritance"
        elif "o--" in rel_type:
            return "aggregation"
        elif "<--" in rel_type:
            return "association"
        elif "<.." in rel_type:
            return "dependency"
        elif ".." in rel_type:
            return "dotted"
        return "association"
    
    def _extract_entities(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract entities from an ER diagram.
        
        Args:
            content: The diagram content
            
        Returns:
            List of entity dictionaries
        """
        entities = []
        entity_pattern = r"([A-Za-z0-9_-]+)\s*{([^}]*)}"
        
        for match in re.finditer(entity_pattern, content):
            entity_name = match.group(1)
            entity_body = match.group(2) if match.group(2) else ""
            
            attributes = []
            for line in entity_body.split("\n"):
                line = line.strip()
                if line:
                    attributes.append(line)
            
            entities.append({
                "id": entity_name,
                "name": entity_name,
                "attributes": attributes
            })
        
        return entities
    
    def _extract_er_relationships(self, content: str) -> List[Dict[str, str]]:
        """
        Extract relationships from an ER diagram.
        
        Args:
            content: The diagram content
            
        Returns:
            List of relationship dictionaries
        """
        relationships = []
        relationship_pattern = r"([A-Za-z0-9_-]+)\s+([A-Za-z0-9_-]+)\s+([A-Za-z0-9_-]+)\s*:\s*\"([^\"]*)\""
        
        for match in re.finditer(relationship_pattern, content):
            source = match.group(1)
            relationship_type = match.group(2)
            target = match.group(3)
            label = match.group(4).strip() if match.group(4) else ""
            
            relationships.append({
                "source": source,
                "target": target,
                "label": label,
                "type": relationship_type
            })
        
        return relationships 