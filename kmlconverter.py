import zipfile
import os
import shutil

# Función para crear la estructura del KMZ a partir de un archivo KML
def create_kmz_from_kml(kml_file, output_kmz):
    # Directorio temporal donde se creará la estructura
    temp_dir = 'temp_kmz'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    # Crear la estructura de carpetas wpmz/
    wpmz_dir = os.path.join(temp_dir, 'wpmz')
    os.makedirs(wpmz_dir, exist_ok=True)

    # Copiar el archivo KML original dentro de la carpeta wpmz
    kml_filename = os.path.basename(kml_file)
    kml_copy_path = os.path.join(wpmz_dir, kml_filename)
    shutil.copy(kml_file, kml_copy_path)

    # Crear el archivo template.kml (esto es solo un ejemplo, crea o usa tu archivo real)
    template_kml = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
    <Document>
        <name>Template</name>
        <Placemark>
            <name>Waypoint</name>
            <Point>
                <coordinates>-122.0822035425683,37.42228990140251,0</coordinates>
            </Point>
        </Placemark>
    </Document>
</kml>'''

    with open(os.path.join(wpmz_dir, 'template.kml'), 'w') as f:
        f.write(template_kml)

    # Crear el archivo waylines.wpml (esto es solo un ejemplo, crea o usa tu archivo real)
    waylines_wpml = '''<waylines>
    <wayline>
        <name>Wayline 1</name>
        <waypoint>Waypoint 1</waypoint>
    </wayline>
</waylines>'''

    with open(os.path.join(wpmz_dir, 'waylines.wpml'), 'w') as f:
        f.write(waylines_wpml)

    # Crear el archivo KMZ a partir del contenido
    kmz_output = os.path.join(os.getcwd(), output_kmz)
    with zipfile.ZipFile(kmz_output, 'w', zipfile.ZIP_DEFLATED) as kmz:
        # Agregar todo el contenido del directorio temporal al archivo KMZ
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                kmz.write(os.path.join(root, file), 
                          os.path.relpath(os.path.join(root, file), temp_dir))

    # Limpiar directorios temporales
    shutil.rmtree(temp_dir)
    print(f"Nuevo archivo KMZ creado: {kmz_output}")

# Función principal para ejecutar el script
def main():
    # Ruta al archivo KML (sin necesidad de modificar el script cada vez)
    input_kml = input("Introduce la ruta del archivo KML: ")  # Te pide la ruta del archivo KML
    output_kmz = input("Introduce el nombre del archivo KMZ de salida: ")  # Te pide el nombre de salida

    if os.path.exists(input_kml):
        create_kmz_from_kml(input_kml, output_kmz)
    else:
        print(f"El archivo KML '{input_kml}' no existe. Por favor, verifica la ruta.")

if __name__ == "__main__":
    main()
