import zipfile
import os
import xml.etree.ElementTree as ET

def extract_and_analyze_kmz(kmz_path, output_dir):
    """Extrae y analiza un archivo KMZ"""
    print(f"\n=== Analizando {os.path.basename(kmz_path)} ===")
    
    # Crear directorio de salida
    os.makedirs(output_dir, exist_ok=True)
    
    # Extraer KMZ
    with zipfile.ZipFile(kmz_path, 'r') as kmz:
        kmz.extractall(output_dir)
        print(f"Archivos extraídos en: {output_dir}")
        
        # Listar contenido
        print("Contenido del KMZ:")
        for file_info in kmz.filelist:
            print(f"  - {file_info.filename} ({file_info.file_size} bytes)")
    
    # Analizar waylines.wpml si existe
    waylines_path = os.path.join(output_dir, 'wpmz', 'waylines.wpml')
    if os.path.exists(waylines_path):
        print(f"\n📄 Analizando waylines.wpml:")
        analyze_waylines_wpml(waylines_path)
    
    # Analizar template.kml si existe
    template_path = os.path.join(output_dir, 'wpmz', 'template.kml')
    if os.path.exists(template_path):
        print(f"\n📄 Analizando template.kml:")
        analyze_template_kml(template_path)

def analyze_waylines_wpml(file_path):
    """Analiza el archivo waylines.wpml"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Buscar waypoints
        waypoints = root.findall('.//{http://www.dji.com/wpmz/1.0.2}waypoint')
        print(f"  Waypoints encontrados: {len(waypoints)}")
        
        # Analizar acciones de foto
        photo_actions = 0
        for waypoint in waypoints:
            actions = waypoint.findall('.//{http://www.dji.com/wpmz/1.0.2}action')
            for action in actions:
                func_elem = action.find('.//{http://www.dji.com/wpmz/1.0.2}actionActuatorFunc')
                if func_elem is not None and func_elem.text == 'takePhoto':
                    photo_actions += 1
                    
                    # Obtener detalles del waypoint
                    waypoint_index = waypoint.find('.//{http://www.dji.com/wpmz/1.0.2}waypointIndex')
                    trigger_type = action.find('.//{http://www.dji.com/wpmz/1.0.2}actionTriggerType')
                    
                    print(f"    📸 Foto en waypoint {waypoint_index.text if waypoint_index is not None else 'N/A'}, trigger: {trigger_type.text if trigger_type is not None else 'N/A'}")
        
        print(f"  📸 Total acciones de foto: {photo_actions}")
        
        # Analizar velocidades
        speeds = set()
        for waypoint in waypoints:
            speed_elem = waypoint.find('.//{http://www.dji.com/wpmz/1.0.2}waypointSpeed')
            if speed_elem is not None:
                speeds.add(speed_elem.text)
        
        print(f"  🚁 Velocidades encontradas: {list(speeds)}")
        
        # Analizar heading y gimbal
        heading_angles = set()
        gimbal_pitches = set()
        for waypoint in waypoints:
            heading_elem = waypoint.find('.//{http://www.dji.com/wpmz/1.0.2}waypointHeadingAngle')
            if heading_elem is not None:
                heading_angles.add(heading_elem.text)
                
            gimbal_elem = waypoint.find('.//{http://www.dji.com/wpmz/1.0.2}gimbalPitchAngle')
            if gimbal_elem is not None:
                gimbal_pitches.add(gimbal_elem.text)
        
        print(f"  🧭 Ángulos de heading: {list(heading_angles)}")
        print(f"  📹 Ángulos de gimbal pitch: {list(gimbal_pitches)}")
        
    except Exception as e:
        print(f"  ❌ Error analizando waylines.wpml: {e}")

def analyze_template_kml(file_path):
    """Analiza el archivo template.kml"""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Buscar configuración global
        auto_speed = root.find('.//{http://www.dji.com/wpmz/1.0.2}autoFlightSpeed')
        if auto_speed is not None:
            print(f"  🚁 Velocidad global: {auto_speed.text}")
        
        # Buscar placemarks (waypoints en template)
        placemarks = root.findall('.//Placemark')
        print(f"  📍 Placemarks en template: {len(placemarks)}")
        
        # Analizar acciones en template
        action_groups = root.findall('.//{http://www.dji.com/wpmz/1.0.2}actionGroup')
        print(f"  🎬 Grupos de acciones: {len(action_groups)}")
        
        for i, group in enumerate(action_groups):
            actions = group.findall('.//{http://www.dji.com/wpmz/1.0.2}action')
            print(f"    Grupo {i}: {len(actions)} acciones")
            
            for action in actions:
                func_elem = action.find('.//{http://www.dji.com/wpmz/1.0.2}actionActuatorFunc')
                if func_elem is not None:
                    print(f"      - {func_elem.text}")
        
    except Exception as e:
        print(f"  ❌ Error analizando template.kml: {e}")

if __name__ == "__main__":
    # Analizar archivo generado por el script
    script_kmz = "c:/Users/garci/Downloads/H2_FlightPlans/lazo1_original.kmz"
    manual_kmz = "c:/Users/garci/Downloads/H2_FlightPlans/New Waypoint Route.kmz"
    
    if os.path.exists(script_kmz):
        extract_and_analyze_kmz(script_kmz, "analysis_script_output")
    else:
        print(f"❌ No se encontró: {script_kmz}")
    
    if os.path.exists(manual_kmz):
        extract_and_analyze_kmz(manual_kmz, "analysis_manual_output")
    else:
        print(f"❌ No se encontró: {manual_kmz}")
    
    print("\n🔍 Análisis completado. Revisa los directorios 'analysis_script_output' y 'analysis_manual_output' para ver los archivos extraídos.")