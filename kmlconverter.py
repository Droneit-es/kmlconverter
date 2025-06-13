import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
import tempfile
import argparse
import time
import math
from datetime import datetime

class KMLToWPMLConverter:
    def __init__(self):
        self.kml_namespace = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Configuración de drones disponibles (actualizada según documentación oficial DJI)
        self.drone_configs = {
            'mavic3t': {
                'enum': 77,
                'name': 'DJI Mavic 3T',
                'subtype': 1,
                'payload_enum': 67,
                'payload_name': 'Mavic 3T Camera',
                'description': 'Mavic 3 Enterprise Series (M3T Camera)'
            },
            'mavic3e': {
                'enum': 77,
                'name': 'DJI Mavic 3E',
                'subtype': 0,
                'payload_enum': 66,
                'payload_name': 'Mavic 3E Camera',
                'description': 'Mavic 3 Enterprise Series (M3E Camera)'
            },
            'matrice4e': {
                'enum': 99,
                'name': 'DJI Matrice 4E',
                'subtype': 0,
                'payload_enum': 88,
                'payload_name': 'DJI Matrice 4E Camera',
                'description': 'DJI Matrice 4 Series (M4E Camera)'
            },
            'matrice4t': {
                'enum': 99,
                'name': 'DJI Matrice 4T',
                'subtype': 1,
                'payload_enum': 89,
                'payload_name': 'DJI Matrice 4T Camera',
                'description': 'DJI Matrice 4 Series (M4T Camera)'
            },
            'matrice350': {
                'enum': 89,
                'name': 'Matrice 350 RTK',
                'subtype': 0,
                'payload_enum': 42,
                'payload_name': 'Zenmuse H20',
                'description': 'Matrice 350 RTK'
            },
            'matrice300': {
                'enum': 60,
                'name': 'Matrice 300 RTK',
                'subtype': 0,
                'payload_enum': 42,
                'payload_name': 'Zenmuse H20',
                'description': 'Matrice 300 RTK'
            },
            'matrice30': {
                'enum': 67,
                'name': 'Matrice 30',
                'subtype': 0,
                'payload_enum': 52,
                'payload_name': 'Matrice 30 Camera',
                'description': 'Matrice 30'
            },
            'matrice30t': {
                'enum': 67,
                'name': 'Matrice 30T',
                'subtype': 1,
                'payload_enum': 53,
                'payload_name': 'Matrice 30T Camera',
                'description': 'Matrice 30T'
            }
        }
        
    def list_available_drones(self):
        """Lista los drones disponibles"""
        print("\n🚁 Drones disponibles:")
        for key, config in self.drone_configs.items():
            print(f"   {key}: {config['description']} ({config['name']})")
        
    def extract_waypoint_actions(self, placemark_elem):
        """Extrae acciones específicas del waypoint desde el KML"""
        actions = {
            'stop_at_waypoint': True,  # Por defecto parar en waypoint
            'photo_action': None,
            'video_action': None,
            'speed': 5.0,
            'heading_mode': 'smoothTransition',
            'heading': None,
            'gimbal_pitch': -90.0,
            'hovering_time': 0
        }
        
        # Buscar elementos de descripción que puedan contener acciones
        description = placemark_elem.find('.//kml:description', self.kml_namespace)
        if description is not None and description.text:
            desc_text = description.text.lower()
            
            # Detectar si es disparo continuo o parada en waypoint
            if 'continuous' in desc_text or 'continuo' in desc_text:
                actions['stop_at_waypoint'] = False
                print(f"      -> Detectado: Disparo continuo")
            elif 'stop' in desc_text or 'parada' in desc_text or 'hover' in desc_text:
                actions['stop_at_waypoint'] = True
                print(f"      -> Detectado: Parada en waypoint")
                
            # Detectar acciones de cámara
            if 'photo' in desc_text or 'foto' in desc_text:
                actions['photo_action'] = 'single'
                print(f"      -> Detectado: Acción de foto")
            elif 'video' in desc_text:
                actions['video_action'] = 'start' if 'start' in desc_text else 'record'
                print(f"      -> Detectado: Acción de video")
        
        # Buscar elementos extendidos de DJI (namespace mis)
        extended_data = placemark_elem.find('.//kml:ExtendedData', self.kml_namespace)
        if extended_data is not None:
            # Buscar elementos con namespace mis (DJI)
            for elem in extended_data.iter():
                tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                
                if tag_name == 'pointType' and elem.text:
                    if elem.text.lower() == 'linestop':
                        actions['stop_at_waypoint'] = True
                        print(f"      -> DJI pointType: LineStop (parada en waypoint)")
                    elif elem.text.lower() == 'line':
                        actions['stop_at_waypoint'] = False
                        print(f"      -> DJI pointType: Line (disparo continuo)")
                
                elif tag_name == 'speed' and elem.text:
                    actions['speed'] = float(elem.text)
                    print(f"      -> Velocidad DJI: {actions['speed']} m/s")
                
                elif tag_name == 'heading' and elem.text:
                    actions['heading'] = float(elem.text)
                    print(f"      -> Heading DJI: {actions['heading']}°")
                
                elif tag_name == 'gimbalPitch' and elem.text:
                    actions['gimbal_pitch'] = float(elem.text)
                    print(f"      -> Gimbal Pitch DJI: {actions['gimbal_pitch']}°")
                
                elif tag_name == 'actions':
                    action_type = elem.text
                    param = elem.get('param', '0')
                    
                    if action_type == 'ShootPhoto':
                        actions['photo_action'] = 'single'
                        print(f"      -> DJI Action: ShootPhoto")
                    elif action_type == 'Hovering':
                        actions['hovering_time'] = int(param) if param.isdigit() else 1000
                        print(f"      -> DJI Action: Hovering {actions['hovering_time']}ms")
                    elif action_type == 'StartRecord':
                        actions['video_action'] = 'start'
                        print(f"      -> DJI Action: StartRecord")
                    elif action_type == 'StopRecord':
                        actions['video_action'] = 'stop'
                        print(f"      -> DJI Action: StopRecord")
        
        # Buscar elementos con namespace mis (DJI) directamente
        mis_namespace = {'mis': 'www.dji.com'}
        for mis_elem in placemark_elem.findall('.//mis:actions', mis_namespace):
            action_type = mis_elem.text
            param = mis_elem.get('param', '0')
            
            if action_type == 'ShootPhoto':
                actions['photo_action'] = 'single'
                print(f"      -> MIS Action: ShootPhoto")
            elif action_type == 'Hovering':
                actions['hovering_time'] = int(param) if param.isdigit() else 1000
                print(f"      -> MIS Action: Hovering {actions['hovering_time']}ms")
        
        # Y hacer lo mismo para speed, pointType, gimbalPitch y heading:
        for speed_elem in placemark_elem.findall('.//mis:speed', mis_namespace):
            if speed_elem.text:
                actions['speed'] = float(speed_elem.text)
                print(f"      -> MIS Speed: {actions['speed']} m/s")
        
        for point_type_elem in placemark_elem.findall('.//mis:pointType', mis_namespace):
            if point_type_elem.text:
                if point_type_elem.text.lower() == 'linestop':
                    actions['stop_at_waypoint'] = True
                    print(f"      -> MIS pointType: LineStop")
                elif point_type_elem.text.lower() == 'line':
                    actions['stop_at_waypoint'] = False
                    print(f"      -> MIS pointType: Line")
        
        for gimbal_elem in placemark_elem.findall('.//mis:gimbalPitch', mis_namespace):
            if gimbal_elem.text:
                actions['gimbal_pitch'] = float(gimbal_elem.text)
                print(f"      -> MIS Gimbal Pitch: {actions['gimbal_pitch']}°")
        
        for heading_elem in placemark_elem.findall('.//mis:heading', mis_namespace):
            if heading_elem.text:
                actions['heading'] = float(heading_elem.text)
                print(f"      -> MIS Heading: {actions['heading']}°")
        
        # Buscar elementos Data tradicionales
        if extended_data is not None:
            for data in extended_data.findall('.//kml:Data', self.kml_namespace):
                name_attr = data.get('name', '').lower()
                value = data.find('.//kml:value', self.kml_namespace)
                
                if value is not None and value.text:
                    if name_attr == 'speed':
                        actions['speed'] = float(value.text)
                        print(f"      -> Velocidad personalizada: {actions['speed']} m/s")
                    elif name_attr == 'action' and 'continuous' in value.text.lower():
                        actions['stop_at_waypoint'] = False
                        print(f"      -> Modo continuo detectado en ExtendedData")
        
        return actions

    def extract_coordinates_from_kml(self, kml_file):
        """Extrae coordenadas y información de waypoints del archivo KML original"""
        print(f"📖 Leyendo archivo KML: {kml_file}")
        
        try:
            tree = ET.parse(kml_file)
            root = tree.getroot()
            
            print(f"   ✓ Archivo KML cargado correctamente")
            print(f"   ✓ Elemento raíz: {root.tag}")
            
            waypoints = []
            
            # Buscar placemarks con coordenadas (con y sin namespace)
            placemarks = root.findall('.//kml:Placemark', self.kml_namespace)
            if not placemarks:
                placemarks = root.findall('.//Placemark')  # Sin namespace
            
            # Filtrar solo placemarks que contengan Point (waypoints individuales)
            point_placemarks = []
            for placemark in placemarks:
                point_elem = placemark.find('.//kml:Point', self.kml_namespace)
                if point_elem is None:
                    point_elem = placemark.find('.//Point')  # Sin namespace
                if point_elem is not None:
                    point_placemarks.append(placemark)
            
            print(f"   ✓ Encontrados {len(placemarks)} Placemarks, {len(point_placemarks)} con Point")
            
            for i, placemark in enumerate(point_placemarks):
                name_elem = placemark.find('.//kml:name', self.kml_namespace)
                if name_elem is None:
                    name_elem = placemark.find('.//name')  # Sin namespace
                
                coordinates_elem = placemark.find('.//kml:coordinates', self.kml_namespace)
                if coordinates_elem is None:
                    coordinates_elem = placemark.find('.//coordinates')  # Sin namespace
                
                if coordinates_elem is not None:
                    coord_text = coordinates_elem.text.strip()
                    print(f"   ✓ Coordenadas encontradas en Placemark {i+1}: {coord_text[:50]}...")
                    
                    # Extraer acciones del waypoint
                    actions = self.extract_waypoint_actions(placemark)
                    
                    try:
                        # Limpiar coordenadas - tomar solo la primera línea si hay múltiples
                        coord_lines = coord_text.split('\n')
                        first_coord = coord_lines[0].strip()
                        
                        # Parsear coordenadas (formato: lon,lat,alt)
                        coords = first_coord.split(',')
                        if len(coords) >= 2:
                            # Validar que los valores sean números válidos
                            lon = float(coords[0].strip())
                            lat = float(coords[1].strip())
                            alt = float(coords[2].strip()) if len(coords) > 2 and coords[2].strip() else 50.0
                            
                            waypoint = {
                                'name': name_elem.text if name_elem is not None else f"Waypoint_{len(waypoints)+1}",
                                'longitude': lon,
                                'latitude': lat,
                                'altitude': alt,
                                'index': len(waypoints),
                                'actions': actions
                            }
                            waypoints.append(waypoint)
                            print(f"      -> Waypoint {waypoint['index']}: {waypoint['name']} ({waypoint['latitude']:.6f}, {waypoint['longitude']:.6f}, {waypoint['altitude']}m)")
                    except (ValueError, IndexError) as e:
                        print(f"   ⚠️  Error al parsear coordenadas en Placemark {i+1}: {e}")
                        print(f"      Coordenadas problemáticas: {coord_text[:100]}...")
                        continue
            
            # Si no encuentra placemarks, buscar en LineString
            if not waypoints:
                print("   ⚠️  No se encontraron Placemarks con coordenadas, buscando en LineString...")
                linestrings = root.findall('.//kml:LineString', self.kml_namespace)
                if not linestrings:
                    linestrings = root.findall('.//LineString')  # Sin namespace
                print(f"   ✓ Encontrados {len(linestrings)} LineStrings")
                
                for linestring in linestrings:
                    coordinates_elem = linestring.find('.//kml:coordinates', self.kml_namespace)
                    if coordinates_elem is None:
                        coordinates_elem = linestring.find('.//coordinates')  # Sin namespace
                    if coordinates_elem is not None:
                        coord_text = coordinates_elem.text.strip()
                        print(f"   ✓ Coordenadas LineString: {coord_text[:100]}...")
                        
                        coord_lines = coord_text.split('\n')
                        for i, line in enumerate(coord_lines):
                            line = line.strip()
                            if line:
                                coords = line.split(',')
                                if len(coords) >= 2:
                                    waypoint = {
                                        'name': f"Waypoint_{i+1}",
                                        'longitude': float(coords[0]),
                                        'latitude': float(coords[1]),
                                        'altitude': float(coords[2]) if len(coords) > 2 else 50.0,
                                        'index': i,
                                        'actions': {'stop_at_waypoint': False, 'speed': 5.0}  # LineString normalmente es continuo
                                    }
                                    waypoints.append(waypoint)
                                    print(f"      -> Waypoint {waypoint['index']}: {waypoint['name']} ({waypoint['latitude']:.6f}, {waypoint['longitude']:.6f}, {waypoint['altitude']}m)")
            
            print(f"   ✅ Total de waypoints extraídos: {len(waypoints)}")
            return waypoints
            
        except Exception as e:
            print(f"   ❌ Error al procesar {kml_file}: {str(e)}")
            return []

    def create_waylines_wpml(self, waypoints, mission_name, drone_type='mavic3t'):
        """Crea el archivo waylines.wpml según especificación WPML oficial"""
        if not waypoints:
            return ""
        
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        if drone_type not in self.drone_configs:
            drone_type = 'mavic3t'
        
        config = self.drone_configs[drone_type]
        
        # Calcular distancia total entre waypoints
        total_distance = 0.0
        total_speed = 0.0
        speed_count = 0
        
        for i in range(1, len(waypoints)):
            lat1, lon1 = waypoints[i-1]['latitude'], waypoints[i-1]['longitude']
            lat2, lon2 = waypoints[i]['latitude'], waypoints[i]['longitude']
            # Fórmula de distancia haversine simplificada para distancias cortas
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            total_distance += 6371000 * c  # Radio de la Tierra en metros
            
            # Acumular velocidades para calcular promedio
            wp_speed = waypoints[i].get('actions', {}).get('speed', 5.0)
            total_speed += wp_speed
            speed_count += 1
        
        # Calcular velocidad promedio
        average_speed = total_speed / speed_count if speed_count > 0 else 5.0
        
        print(f"   📏 Distancia total calculada: {total_distance:.2f} metros")
        print(f"   🚀 Velocidad promedio: {average_speed:.1f} m/s")
        print(f"   ⏱️  Tiempo estimado de vuelo: {int((total_distance / average_speed) / 60)} minutos")
        
        # Detectar modo predominante de vuelo
        continuous_count = sum(1 for wp in waypoints if not wp.get('actions', {}).get('stop_at_waypoint', True))
        is_continuous_flight = continuous_count > len(waypoints) / 2
        
        print(f"   📊 Análisis de vuelo:")
        print(f"      - Waypoints continuos: {continuous_count}/{len(waypoints)}")
        print(f"      - Modo detectado: {'Continuo' if is_continuous_flight else 'Parada en waypoints'}")
        print(f"      - Distancia total: {total_distance:.1f}m")
        
        wpml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.dji.com/wpmz/1.0.6">
  <Document>
    <wpml:author>DJI Pilot</wpml:author>
    <wpml:createTime>{current_time}</wpml:createTime>
    <wpml:updateTime>{current_time}</wpml:updateTime>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>goHome</wpml:finishAction>
      <wpml:exitOnRCLost>executeLostAction</wpml:exitOnRCLost>
      <wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>
      <wpml:takeOffSecurityHeight>20</wpml:takeOffSecurityHeight>
      <wpml:globalTransitionalSpeed>5</wpml:globalTransitionalSpeed>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateType>waypoint</wpml:templateType>
      <wpml:templateId>0</wpml:templateId>
      <wpml:executeHeightMode>relativeToStartPoint</wpml:executeHeightMode>
      <wpml:waylineCoordinateSysParam>
        <wpml:coordinateMode>WGS84</wpml:coordinateMode>
        <wpml:heightMode>relativeToStartPoint</wpml:heightMode>
      </wpml:waylineCoordinateSysParam>
      <wpml:autoFlightSpeed>5</wpml:autoFlightSpeed>
      <wpml:transitionalSpeed>5</wpml:transitionalSpeed>
      <Placemark>
        <n>{mission_name}</n>
        <wpml:index>0</wpml:index>
        <wpml:executeHeight>{waypoints[0]['altitude']}</wpml:executeHeight>
        <wpml:waylineId>0</wpml:waylineId>
        <wpml:distance>{total_distance:.2f}</wpml:distance>
        <wpml:duration>{int((total_distance / average_speed) + (len(waypoints) * 2))}</wpml:duration>
        <wpml:autoFlightSpeed>5</wpml:autoFlightSpeed>
        <LineString>
          <tessellate>1</tessellate>
          <altitudeMode>relativeToGround</altitudeMode>
          <coordinates>'''
        
        # Agregar coordenadas de la línea
        for wp in waypoints:
            wpml_content += f"\n            {wp['longitude']},{wp['latitude']},{wp['altitude']}"
        
        wpml_content += '''
          </coordinates>
        </LineString>'''
        
        # Agregar waypoints individuales con sus acciones específicas
        for wp in waypoints:
            actions = wp.get('actions', {})
            stop_at_wp = actions.get('stop_at_waypoint', True)
            wp_speed = actions.get('speed', 5.0)
            heading = actions.get('heading')
            gimbal_pitch = actions.get('gimbal_pitch', -90.0)
            hovering_time = actions.get('hovering_time', 0)
            
            # Determinar modo de giro basado en si para o no
            turn_mode = "toPointAndStopWithDiscontinuityCurvature" if stop_at_wp else "toPointAndPassWithContinuityCurvature"
            
            # Determinar modo de heading
            heading_mode = "smoothTransition"
            if heading is not None:
                heading_mode = "followWayline"
            
            wpml_content += f'''
        <wpml:waypoint>
          <wpml:index>{wp['index']}</wpml:index>
          <wpml:location>
            <wpml:height>{wp['altitude']}</wpml:height>
            <wpml:latitude>{wp['latitude']}</wpml:latitude>
            <wpml:longitude>{wp['longitude']}</wpml:longitude>
          </wpml:location>
          <wpml:waypointSpeed>{wp_speed}</wpml:waypointSpeed>
          <wpml:waypointHeadingParam>
            <wpml:waypointHeadingMode>{heading_mode}</wpml:waypointHeadingMode>'''
            
            if heading is not None:
                wpml_content += f'''
            <wpml:waypointHeadingAngle>{heading}</wpml:waypointHeadingAngle>'''
            
            wpml_content += f'''
          </wpml:waypointHeadingParam>
          <wpml:waypointTurnParam>
            <wpml:waypointTurnMode>{turn_mode}</wpml:waypointTurnMode>
          </wpml:waypointTurnParam>
          <wpml:useStraightLine>1</wpml:useStraightLine>
          <wpml:gimbalPitchParam>
            <wpml:gimbalPitchMode>usePointSetting</wpml:gimbalPitchMode>
            <wpml:gimbalPitchAngle>{gimbal_pitch}</wpml:gimbalPitchAngle>
          </wpml:gimbalPitchParam>'''
            
            # Agregar acciones si existen
            action_count = 0
            if actions.get('photo_action') or hovering_time > 0 or actions.get('video_action'):
                wpml_content += f'''
          <wpml:actionGroup>
            <wpml:actionGroupId>{wp['index']}</wpml:actionGroupId>
            <wpml:actionGroupStartIndex>{wp['index']}</wpml:actionGroupStartIndex>
            <wpml:actionGroupEndIndex>{wp['index']}</wpml:actionGroupEndIndex>
            <wpml:actionGroupMode>sequence</wpml:actionGroupMode>
            <wpml:actionTrigger>
              <wpml:actionTriggerType>reachPoint</wpml:actionTriggerType>
            </wpml:actionTrigger>'''
                
                # Acción de hovering (pausa)
                if hovering_time > 0:
                    wpml_content += f'''
            <wpml:action>
              <wpml:actionId>{action_count}</wpml:actionId>
              <wpml:actionActuatorFunc>hover</wpml:actionActuatorFunc>
              <wpml:actionActuatorFuncParam>
                <wpml:hoverTime>{hovering_time}</wpml:hoverTime>
              </wpml:actionActuatorFuncParam>
            </wpml:action>'''
                    action_count += 1
                
                # Acción de foto
                if actions.get('photo_action'):
                    wpml_content += f'''
            <wpml:action>
              <wpml:actionId>{action_count}</wpml:actionId>
              <wpml:actionActuatorFunc>takePhoto</wpml:actionActuatorFunc>
              <wpml:actionActuatorFuncParam>
                <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
              </wpml:actionActuatorFuncParam>
            </wpml:action>'''
                    action_count += 1
                
                # Acción de video
                if actions.get('video_action'):
                    video_func = "startRecord" if actions['video_action'] == 'start' else "stopRecord"
                    wpml_content += f'''
            <wpml:action>
              <wpml:actionId>{action_count}</wpml:actionId>
              <wpml:actionActuatorFunc>{video_func}</wpml:actionActuatorFunc>
              <wpml:actionActuatorFuncParam>
                <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
              </wpml:actionActuatorFuncParam>
            </wpml:action>'''
                    action_count += 1
                
                wpml_content += '''
          </wpml:actionGroup>'''
            
            wpml_content += '''
        </wpml:waypoint>'''
        
        wpml_content += '''
      </Placemark>
    </Folder>
  </Document>
</kml>'''
        
        return wpml_content

    def create_template_file(self, waypoints, drone_type='mavic3t'):
        """Crea el archivo template.kml según especificación WPML oficial"""
        if drone_type not in self.drone_configs:
            print(f"⚠️  Drone {drone_type} no reconocido, usando Mavic 3T por defecto")
            drone_type = 'mavic3t'
        
        config = self.drone_configs[drone_type]
        print(f"   🚁 Configurando para: {config['description']}")
        
        current_time = int(time.time() * 1000)
        
        # Calcular punto de referencia de despegue (primer waypoint)
        takeoff_point = f"{waypoints[0]['latitude']},{waypoints[0]['longitude']},{waypoints[0]['altitude']}"
        
        template_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.dji.com/wpmz/1.0.2">
  <Document>
    <wpml:author>DJI Pilot</wpml:author>
    <wpml:createTime>{current_time}</wpml:createTime>
    <wpml:updateTime>{current_time}</wpml:updateTime>
    <wpml:missionConfig>
      <wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
      <wpml:finishAction>goHome</wpml:finishAction>
      <wpml:exitOnRCLost>goContinue</wpml:exitOnRCLost>
      <wpml:executeRCLostAction>hover</wpml:executeRCLostAction>
      <wpml:takeOffSecurityHeight>20</wpml:takeOffSecurityHeight>
      <wpml:takeOffRefPoint>{takeoff_point}</wpml:takeOffRefPoint>
      <wpml:takeOffRefPointAGLHeight>{waypoints[0]['altitude']}</wpml:takeOffRefPointAGLHeight>
      <wpml:globalTransitionalSpeed>8</wpml:globalTransitionalSpeed>
      <wpml:droneInfo>
        <wpml:droneEnumValue>{config['enum']}</wpml:droneEnumValue>
        <wpml:droneSubEnumValue>{config['subtype']}</wpml:droneSubEnumValue>
      </wpml:droneInfo>
      <wpml:payloadInfo>
        <wpml:payloadEnumValue>{config['payload_enum']}</wpml:payloadEnumValue>
        <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
      </wpml:payloadInfo>
    </wpml:missionConfig>
    <Folder>
      <wpml:templateType>waypoint</wpml:templateType>
      <wpml:templateId>0</wpml:templateId>
      <wpml:waylineCoordinateSysParam>
        <wpml:coordinateMode>WGS84</wpml:coordinateMode>
        <wpml:heightMode>EGM96</wpml:heightMode>
        <wpml:globalShootHeight>{waypoints[0]['altitude']}</wpml:globalShootHeight>
        <wpml:positioningType>GPS</wpml:positioningType>
        <wpml:surfaceFollowModeEnable>0</wpml:surfaceFollowModeEnable>
        <wpml:surfaceRelativeHeight>100</wpml:surfaceRelativeHeight>
      </wpml:waylineCoordinateSysParam>
      <wpml:autoFlightSpeed>5</wpml:autoFlightSpeed>
      <wpml:gimbalPitchMode>usePointSetting</wpml:gimbalPitchMode>
      <wpml:globalWaypointHeadingParam>
        <wpml:waypointHeadingMode>followWayline</wpml:waypointHeadingMode>
        <wpml:waypointHeadingAngle>0</wpml:waypointHeadingAngle>
        <wpml:waypointHeadingPathMode>clockwise</wpml:waypointHeadingPathMode>
      </wpml:globalWaypointHeadingParam>
      <wpml:globalWaypointTurnMode>toPointAndStopWithDiscontinuityCurvature</wpml:globalWaypointTurnMode>
      <wpml:globalUseStraightLine>1</wpml:globalUseStraightLine>'''
        
        # Agregar waypoints al template
        for wp in waypoints:
            actions = wp.get('actions', {})
            gimbal_pitch = actions.get('gimbal_pitch', -90.0)
            heading = actions.get('heading', 0)
            
            template_content += f'''
      <Placemark>
        <Point>
          <coordinates>{wp['longitude']},{wp['latitude']}</coordinates>
        </Point>
        <wpml:index>{wp['index']}</wpml:index>
        <wpml:ellipsoidHeight>{wp['altitude']}</wpml:ellipsoidHeight>
        <wpml:height>{wp['altitude']}</wpml:height>
        <wpml:useGlobalHeight>0</wpml:useGlobalHeight>
        <wpml:useGlobalSpeed>0</wpml:useGlobalSpeed>
        <wpml:useGlobalHeadingParam>0</wpml:useGlobalHeadingParam>
        <wpml:useGlobalTurnParam>1</wpml:useGlobalTurnParam>
        <wpml:gimbalPitchAngle>{gimbal_pitch}</wpml:gimbalPitchAngle>'''
            
            # Agregar actionGroup si hay acciones de foto
            if actions.get('photo_action') or actions.get('hovering_time', 0) > 0:
                import uuid
                action_uuid = str(uuid.uuid4())
                
                template_content += f'''
        <wpml:actionGroup>
          <wpml:actionGroupId>{wp['index']}</wpml:actionGroupId>
          <wpml:actionGroupStartIndex>{wp['index']}</wpml:actionGroupStartIndex>
          <wpml:actionGroupEndIndex>{wp['index']}</wpml:actionGroupEndIndex>
          <wpml:actionGroupMode>sequence</wpml:actionGroupMode>
          <wpml:actionTrigger>
            <wpml:actionTriggerType>reachPoint</wpml:actionTriggerType>
          </wpml:actionTrigger>'''
                
                action_id = 0
                
                # Agregar acción de rotación si hay heading específico
                if heading != 0:
                    template_content += f'''
          <wpml:action>
            <wpml:actionId>{action_id}</wpml:actionId>
            <wpml:actionActuatorFunc>rotateYaw</wpml:actionActuatorFunc>
            <wpml:actionActuatorFuncParam>
              <wpml:aircraftHeading>{heading}</wpml:aircraftHeading>
              <wpml:aircraftPathMode>clockwise</wpml:aircraftPathMode>
            </wpml:actionActuatorFuncParam>
          </wpml:action>'''
                    action_id += 1
                
                # Agregar acción de gimbal
                template_content += f'''
          <wpml:action>
            <wpml:actionId>{action_id}</wpml:actionId>
            <wpml:actionActuatorFunc>gimbalRotate</wpml:actionActuatorFunc>
            <wpml:actionActuatorFuncParam>
              <wpml:gimbalHeadingYawBase>north</wpml:gimbalHeadingYawBase>
              <wpml:gimbalRotateMode>absoluteAngle</wpml:gimbalRotateMode>
              <wpml:gimbalPitchRotateEnable>1</wpml:gimbalPitchRotateEnable>
              <wpml:gimbalPitchRotateAngle>{gimbal_pitch}</wpml:gimbalPitchRotateAngle>
              <wpml:gimbalRollRotateEnable>0</wpml:gimbalRollRotateEnable>
              <wpml:gimbalRollRotateAngle>0</wpml:gimbalRollRotateAngle>
              <wpml:gimbalYawRotateEnable>0</wpml:gimbalYawRotateEnable>
              <wpml:gimbalYawRotateAngle>0</wpml:gimbalYawRotateAngle>
              <wpml:gimbalRotateTimeEnable>0</wpml:gimbalRotateTimeEnable>
              <wpml:gimbalRotateTime>0</wpml:gimbalRotateTime>
              <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
            </wpml:actionActuatorFuncParam>
          </wpml:action>'''
                action_id += 1
                
                # Agregar acción de zoom
                template_content += f'''
          <wpml:action>
            <wpml:actionId>{action_id}</wpml:actionId>
            <wpml:actionActuatorFunc>zoom</wpml:actionActuatorFunc>
            <wpml:actionActuatorFuncParam>
              <wpml:focalLength>24</wpml:focalLength>
              <wpml:isUseFocalFactor>0</wpml:isUseFocalFactor>
              <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
            </wpml:actionActuatorFuncParam>
          </wpml:action>'''
                action_id += 1
                
                # Agregar acción de foto si está presente
                if actions.get('photo_action'):
                    template_content += f'''
          <wpml:action>
            <wpml:actionId>{action_id}</wpml:actionId>
            <wpml:actionActuatorFunc>orientedShoot</wpml:actionActuatorFunc>
            <wpml:actionActuatorFuncParam>
              <wpml:gimbalPitchRotateAngle>{gimbal_pitch}</wpml:gimbalPitchRotateAngle>
              <wpml:gimbalRollRotateAngle>0</wpml:gimbalRollRotateAngle>
              <wpml:gimbalYawRotateAngle>0</wpml:gimbalYawRotateAngle>
              <wpml:focusX>0</wpml:focusX>
              <wpml:focusY>0</wpml:focusY>
              <wpml:focusRegionWidth>0</wpml:focusRegionWidth>
              <wpml:focusRegionHeight>0</wpml:focusRegionHeight>
              <wpml:focalLength>24</wpml:focalLength>
              <wpml:aircraftHeading>{heading}</wpml:aircraftHeading>
              <wpml:accurateFrameValid>0</wpml:accurateFrameValid>
              <wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
              <wpml:useGlobalPayloadLensIndex>1</wpml:useGlobalPayloadLensIndex>
              <wpml:targetAngle>0</wpml:targetAngle>
              <wpml:actionUUID>{action_uuid}</wpml:actionUUID>
              <wpml:imageWidth>0</wpml:imageWidth>
              <wpml:imageHeight>0</wpml:imageHeight>
              <wpml:AFPos>0</wpml:AFPos>
              <wpml:gimbalPort>0</wpml:gimbalPort>
              <wpml:orientedCameraType>{config['payload_enum']}</wpml:orientedCameraType>
              <wpml:orientedFilePath>{action_uuid}</wpml:orientedFilePath>
              <wpml:orientedFileMD5/>
              <wpml:orientedFileSize>0</wpml:orientedFileSize>
              <wpml:orientedPhotoMode>normalPhoto</wpml:orientedPhotoMode>
            </wpml:actionActuatorFuncParam>
          </wpml:action>'''
                
                template_content += '''
        </wpml:actionGroup>'''
            
            template_content += '''
        <wpml:isRisky>0</wpml:isRisky>
      </Placemark>'''
        
        template_content += '''
    </Folder>
  </Document>
</kml>'''
        
        return template_content

    def convert_kml_to_wpml(self, input_file, output_file, drone_type='mavic3t'):
        """Convierte un archivo KML a formato WPML y crea un KMZ"""
        print(f"\n🔄 Iniciando conversión:")
        print(f"   📁 Entrada: {os.path.abspath(input_file)}")
        print(f"   🚁 Drone seleccionado: {self.drone_configs.get(drone_type, {}).get('description', drone_type)}")
        
        waypoints = self.extract_coordinates_from_kml(input_file)
        
        if not waypoints:
            print(f"   ❌ No se encontraron waypoints válidos en {input_file}")
            return False
        
        # Obtener nombre base del archivo de entrada
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        
        # Limpiar caracteres no soportados por FlightHub
        # FlightHub no soporta: < > : " / | ? * . _ \
        invalid_chars = '<>:"/|?*._\\'
        clean_name = base_name
        for char in invalid_chars:
            clean_name = clean_name.replace(char, '')
        
        # Usar el nombre limpio como mission_name
        mission_name = clean_name
        
        # Generar nombre de salida basado en el directorio de salida y el nombre limpio
        output_dir = os.path.dirname(output_file) if os.path.dirname(output_file) else '.'
        output_file = os.path.join(output_dir, clean_name + '.kmz')
        
        print(f"   📁 Salida: {os.path.abspath(output_file)}")
        
        try:
            # Crear contenido WPML
            wpml_content = self.create_waylines_wpml(waypoints, mission_name, drone_type)
            template_content = self.create_template_file(waypoints, drone_type)
            
            # Crear archivo KMZ (que es un ZIP con estructura específica)
            with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as kmz:
                # Agregar archivo principal wpmz/waylines.wpml
                kmz.writestr('wpmz/waylines.wpml', wpml_content.encode('utf-8'))
                print(f"   ✓ Agregado waylines.wpml al KMZ")
                
                # Agregar template.kml
                kmz.writestr('wpmz/template.kml', template_content.encode('utf-8'))
                print(f"   ✓ Agregado template.kml al KMZ")
            
            print(f"   ✅ Archivo KMZ creado exitosamente en: {os.path.abspath(output_file)}")
            print(f"   📊 Estadísticas:")
            print(f"      - Waypoints procesados: {len(waypoints)}")
            print(f"      - Primer waypoint: {waypoints[0]['name']} ({waypoints[0]['latitude']:.6f}, {waypoints[0]['longitude']:.6f})")
            print(f"      - Último waypoint: {waypoints[-1]['name']} ({waypoints[-1]['latitude']:.6f}, {waypoints[-1]['longitude']:.6f})")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error al crear KMZ {output_file}: {str(e)}")
            return False

    def batch_convert(self, input_dir, output_dir, drone_type='mavic3t'):
        """Convierte múltiples archivos KML en un directorio"""
        print(f"\n🔄 Iniciando conversión en lote:")
        print(f"   📁 Directorio de entrada: {os.path.abspath(input_dir)}")
        print(f"   📁 Directorio de salida: {os.path.abspath(output_dir)}")
        print(f"   🚁 Drone seleccionado: {self.drone_configs.get(drone_type, {}).get('description', drone_type)}")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"   ✓ Directorio de salida creado")
        
        kml_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.kml')]
        
        if not kml_files:
            print(f"   ❌ No se encontraron archivos KML en {input_dir}")
            return
        
        print(f"   📋 Encontrados {len(kml_files)} archivos KML para convertir")
        
        successful = 0
        failed = 0
        
        for i, kml_file in enumerate(kml_files, 1):
            print(f"\n--- Procesando archivo {i}/{len(kml_files)} ---")
            input_path = os.path.join(input_dir, kml_file)
            # Limpiar nombre del archivo para FlightHub
            base_name = os.path.splitext(kml_file)[0]
            invalid_chars = '<>:"/|?*._\\'
            clean_name = base_name
            for char in invalid_chars:
                clean_name = clean_name.replace(char, '')
            
            output_name = clean_name + '.kmz'
            output_path = os.path.join(output_dir, output_name)
            
            if self.convert_kml_to_wpml(input_path, output_path, drone_type):
                successful += 1
            else:
                failed += 1
        
        print(f"\n" + "="*50)
        print(f"📊 RESUMEN DE CONVERSIÓN")
        print(f"="*50)
        print(f"✅ Exitosos: {successful}")
        print(f"❌ Fallidos: {failed}")
        print(f"📋 Total procesados: {len(kml_files)}")
        print(f"📁 Archivos KMZ generados en: {os.path.abspath(output_dir)}")

def main():
    parser = argparse.ArgumentParser(description='Convertir archivos KML de DJI Pilot a formato WPML (.kmz) para FlightHub 2')
    parser.add_argument('input', nargs='?', help='Archivo KML de entrada o directorio con archivos KML')
    parser.add_argument('output', nargs='?', help='Archivo KMZ de salida o directorio de salida')
    parser.add_argument('--drone', '-d', choices=['mavic3t', 'mavic3e', 'matrice4e', 'matrice4t', 'matrice350', 'matrice300', 'matrice30', 'matrice30t'], 
                        default='mavic3t', help='Tipo de drone (default: mavic3t)')
    parser.add_argument('--batch', action='store_true', help='Modo lote para convertir múltiples archivos')
    parser.add_argument('--list-drones', action='store_true', help='Listar drones disponibles')
    
    args = parser.parse_args()
    
    converter = KMLToWPMLConverter()
    
    if args.list_drones:
        converter.list_available_drones()
        return
    
    if not args.input or not args.output:
        print("🚁 Conversor KML a WPML para DJI FlightHub 2")
        print("=" * 50)
        converter.list_available_drones()
        print("\nUso:")
        print("  python script.py archivo.kml salida.kmz --drone mavic3t")
        print("  python script.py carpeta_kml carpeta_salida --batch --drone matrice4e")
        print("  python script.py --list-drones")
        return
    
    if args.batch or os.path.isdir(args.input):
        # Conversión en lote
        converter.batch_convert(args.input, args.output, args.drone)
    else:
        # Conversión individual
        converter.convert_kml_to_wpml(args.input, args.output, args.drone)

if __name__ == "__main__":
    main()