import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Union
from collections import defaultdict
import logging
import yaml
from lxml import etree

# Logger-Konfiguration
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class CityGMLAnalyzer:
    """Analyzer für CityGML-Strukturen."""

    def __init__(self):
        self.stats = {
            'namespaces': {},
            'tag_counts': defaultdict(int),
            'attribute_keys': set(),
            'lod_levels': defaultdict(int),
            'building_count': 0,
            'pos_list_stats': {
                'count': 0,
                'min_coords': float('inf'),
                'max_coords': 0,
                'total_coords': 0
            },
            'xpaths': set(),
            'crs': None,
            'fields_detected': set()
        }

    def _analyze_pos_list(self, pos_list: etree.Element) -> None:
        if pos_list is not None and pos_list.text:
            coords = pos_list.text.strip().split()
            coord_count = len(coords) // 3
            self.stats['pos_list_stats']['count'] += 1
            self.stats['pos_list_stats']['min_coords'] = min(
                self.stats['pos_list_stats']['min_coords'], coord_count)
            self.stats['pos_list_stats']['max_coords'] = max(
                self.stats['pos_list_stats']['max_coords'], coord_count)
            self.stats['pos_list_stats']['total_coords'] += coord_count

    def _analyze_building(self, building: etree.Element, nsmap: Dict[str, str], tree: etree._ElementTree) -> None:
        for el in building.iter():
            tag_clean = etree.QName(el).localname
            tag_ns = etree.QName(el).namespace
            if tag_ns in nsmap.values():
                ns_prefix = [k for k, v in nsmap.items() if v == tag_ns][0]
                tag_full = f"{ns_prefix}:{tag_clean}"
            else:
                tag_full = tag_clean
            self.stats['tag_counts'][tag_full] += 1
            try:
                xpath = tree.getpath(el)
                self.stats['xpaths'].add(xpath)
            except Exception:
                pass

        for attr in building.attrib.keys():
            self.stats['attribute_keys'].add(attr)

        for lod in range(4, -1, -1):
            for geom_type in ['Solid', 'MultiSurface', 'MultiCurve', 'MultiPoint']:
                xpath = f'.//bldg:lod{lod}{geom_type}'
                if building.find(xpath, namespaces=nsmap) is not None:
                    self.stats['lod_levels'][f'LoD{lod}'] += 1
                    break

        for pos_list in building.findall('.//gml:posList', namespaces=nsmap):
            self._analyze_pos_list(pos_list)

        known_fields = ['yearOfConstruction', 'measuredHeight', 'function', 'usage',
                        'storeysAboveGround', 'roofType', 'class']
        for field in known_fields:
            if building.find(f'.//bldg:{field}', namespaces=nsmap) is not None:
                self.stats['fields_detected'].add(field)

    def analyze_file(self, gml_path: Union[str, Path], output_format: str = 'terminal') -> Optional[Dict]:
        try:
            logger.info(f"\U0001F4C2 Starte Analyse der Datei: {gml_path}")
            parser = etree.XMLParser(load_dtd=True, recover=True)
            tree = etree.parse(str(gml_path), parser)
            root = tree.getroot()
            nsmap = dict(root.nsmap)
            self.stats['namespaces'] = nsmap

            envelope = root.find('.//gml:Envelope', namespaces=nsmap)
            if envelope is not None:
                self.stats['crs'] = envelope.get('srsName')

            buildings = tree.findall('.//bldg:Building', namespaces=nsmap)
            self.stats['building_count'] = len(buildings)

            logger.info(f"\U0001F50D Gefundene Gebäude: {len(buildings)}\n")

            for building in buildings:
                self._analyze_building(building, nsmap, tree)

            if output_format == 'terminal':
                self._print_report()
            elif output_format == 'yaml':
                return self._generate_yaml()
            elif output_format == 'dict':
                return dict(self.stats)

        except Exception as e:
            logger.error(f"❌ Fehler bei der Analyse: {str(e)}")
            return None

    def _print_report(self) -> None:
        logger.info("\n🌐 XML-Namespaces:")
        for prefix, uri in self.stats['namespaces'].items():
            logger.info(f" - {prefix}: {uri}")

        logger.info("\n📌 Gefundene Tags (Top 10):")
        sorted_tags = sorted(self.stats['tag_counts'].items(), key=lambda x: -x[1])
        for tag, count in sorted_tags[:10]:
            logger.info(f" - {tag}: {count}x")

        logger.info("\n🔑 Gefundene Attribute:")
        for attr in sorted(self.stats['attribute_keys']):
            logger.info(f" - {attr}")

        logger.info("\n📐 LoD-Level-Verteilung:")
        for lod, count in sorted(self.stats['lod_levels'].items()):
            logger.info(f" - {lod}: {count} Gebäude")

        if self.stats['crs']:
            logger.info(f"\n🗺️  Entdecktes Koordinatensystem (CRS): {self.stats['crs']}")

        if self.stats['pos_list_stats']['count'] > 0:
            avg_coords = self.stats['pos_list_stats']['total_coords'] / self.stats['pos_list_stats']['count']
            logger.info("\n📊 posList-Statistiken:")
            logger.info(f" - Anzahl: {self.stats['pos_list_stats']['count']}")
            logger.info(f" - Min. Koordinaten: {self.stats['pos_list_stats']['min_coords']}")
            logger.info(f" - Max. Koordinaten: {self.stats['pos_list_stats']['max_coords']}")
            logger.info(f" - Durchschnitt: {avg_coords:.1f}")

        if self.stats['fields_detected']:
            logger.info("\n📋 Erkannte CityGML-Felder:")
            for field in sorted(self.stats['fields_detected']):
                logger.info(f" - {field}")

        logger.info("\n✅ Analyse abgeschlossen.\n")

    def _generate_yaml(self) -> str:
        yaml_stats = dict(self.stats)
        yaml_stats['tag_counts'] = dict(yaml_stats['tag_counts'])
        yaml_stats['attribute_keys'] = list(yaml_stats['attribute_keys'])
        yaml_stats['xpaths'] = sorted(list(yaml_stats['xpaths']))
        yaml_stats['fields_detected'] = sorted(list(yaml_stats['fields_detected']))
        return yaml.dump(yaml_stats, allow_unicode=True, sort_keys=False)

def analyze_citygml_structure(gml_path: Union[str, Path], output_format: str = 'terminal') -> Optional[Dict]:
    analyzer = CityGMLAnalyzer()
    return analyzer.analyze_file(gml_path, output_format)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        gml_file = Path(sys.argv[1])
    else:
        root_dir = Path(__file__).resolve().parent.parent.parent
        gml_file = root_dir / "data" / "raw" / "citygml" / "099082.gml"

    analyze_citygml_structure(gml_file)
