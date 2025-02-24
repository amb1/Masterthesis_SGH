import yaml
import subprocess
from pathlib import Path
import os

def run_cea_workflow(scenario_path):
    """
    Führt den CEA-Workflow für ein gegebenes Szenario aus
    """
    try:
        # Ermittle den project_root (analog zu run_cea.py)
        script_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        project_root = script_path
        
        # Verwende die gleiche Pfadlogik wie in run_cea.py
        cea_config_path = os.path.join(project_root, 'cfg', 'cea_config.yml')
        cea_workflow_path = os.path.join(project_root, 'cfg', 'cea_workflow.yml')
        
        print(f"Verwende Konfiguration: {cea_config_path}")
        print(f"Verwende Workflow: {cea_workflow_path}")
        
        # Lade Konfigurationen
        with open(cea_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        with open(cea_workflow_path, 'r', encoding='utf-8') as f:
            workflow = yaml.safe_load(f)
        
        # Basis-Pfade holen (oder per .get prüfen)
        weather_base = config['paths']['weather_base']
        database_base = config['paths']['database_base']
        cea_env_path = config['paths']['cea_env_path']
        
        # ERSTER Eintrag in der workflow-Liste => Dictionary mit "weather-helper:weather" etc.
        if len(workflow) == 0 or not isinstance(workflow[0], dict):
            raise ValueError("Workflow-Definition (cea_workflow.yml) scheint ungültig zu sein!")
        
        # "Ergänzende Einträge aus der cea_workflow.yml
        # "DE" => => "{database_base}/DE"
        workflow[0]['weather-helper:weather'] = f"{weather_base}/{workflow[0]['weather-helper:weather']}"
        workflow[0]['data-initializer:databases-path'] = f"{database_base}/{workflow[0]['data-initializer:databases-path']}"
        
        # Temporäre Workflow-Datei erzeugen (oder überschreiben)
        merged_workflow_path = os.path.join(project_root, 'cfg', 'cea_workflow_merged.yml')
        with open(merged_workflow_path, 'w', encoding='utf-8') as mwf:
            yaml.safe_dump(workflow, mwf, sort_keys=False, default_flow_style=False)
        
        # CEA-Befehl aufrufen mit dem _zusammengeführten_ Workflow
        cea_command = f'cea workflow --workflow "{merged_workflow_path}" --scenario "{scenario_path}"'
        
        print("Starte CEA-Workflow mit folgendem Befehl:")
        print(cea_command)
        
        # Ausführen der cea-env.bat und dann den CEA-Befehl
        subprocess.run(['cmd', '/c', cea_env_path, '&&', cea_command], check=True)
    except Exception as e:
        print(f"Fehler beim Ausführen des CEA-Workflows: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Führt den CEA-Workflow aus')
    parser.add_argument('--scenario', type=str, required=True, help='Pfad zum Szenario-Ordner')
    args = parser.parse_args()

    run_cea_workflow(args.scenario)