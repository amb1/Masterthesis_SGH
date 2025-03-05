import yaml
import subprocess
from pathlib import Path
import os

def run_cea_workflow(scenario_path):
    """
    Führt den CEA-Workflow für ein gegebenes Szenario aus
    """
    try:
        # Ermittle den project_root
        script_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        project_root = script_path
        
        # Lade Konfigurationen
        configs = {
            'common': load_config(os.path.join(project_root, 'cfg', 'common_config.yml')),
            'cea': load_config(os.path.join(project_root, 'cfg', 'cea_config.yml')),
            'workflow': load_config(os.path.join(project_root, 'cfg', 'cea_workflow.yml'))
        }
        
        # Validiere Konfigurationen
        if not all(configs.values()):
            raise ValueError("Fehler beim Laden der Konfigurationen")
            
        # Basis-Pfade aus CEA-Konfiguration
        config = configs['cea']
        weather_base = config['paths']['weather_base']
        database_base = config['paths']['database_base']
        cea_env_path = config['paths']['cea_env_path']
        
        # Workflow-Konfiguration
        workflow = configs['workflow']
        
        # Validiere Workflow
        if len(workflow) == 0 or not isinstance(workflow[0], dict):
            raise ValueError("Workflow-Definition (cea_workflow.yml) scheint ungültig zu sein!")
        
        # Ergänze Pfade
        workflow[0]['weather-helper:weather'] = f"{weather_base}/{workflow[0]['weather-helper:weather']}"
        workflow[0]['data-initializer:databases-path'] = f"{database_base}/{workflow[0]['data-initializer:databases-path']}"
        
        # Temporäre Workflow-Datei
        merged_workflow_path = os.path.join(project_root, 'cfg', 'cea_workflow_merged.yml')
        with open(merged_workflow_path, 'w', encoding='utf-8') as mwf:
            yaml.safe_dump(workflow, mwf, sort_keys=False, default_flow_style=False)
        
        # CEA-Befehl
        cea_command = f'cea workflow --workflow "{merged_workflow_path}" --scenario "{scenario_path}"'
        
        print("Starte CEA-Workflow mit folgendem Befehl:")
        print(cea_command)
        
        # Ausführen
        subprocess.run(['cmd', '/c', cea_env_path, '&&', cea_command], check=True)
        
    except Exception as e:
        print(f"Fehler beim Ausführen des CEA-Workflows: {e}")
        raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Führt den CEA-Workflow aus')
    parser.add_argument('--scenario', type=str, required=True, help='Pfad zum Szenario-Ordner')
    args = parser.parse_args()

    run_cea_workflow(args.scenario)