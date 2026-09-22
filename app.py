import os
import zipfile
import subprocess
import shutil
import tempfile
import io
from flask import Flask, request, send_file, render_template, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/build', methods=['POST'])
def build_plugin():
    if 'file' not in request.files:
        return jsonify({'error': 'Koi file upload nahi ki gayi.'}), 400
    
    file = request.files['file']
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'Sirf .zip files allowed hain.'}), 400

    # Temporary directory banayein file extract karne ke liye
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, 'upload.zip')
    file.save(zip_path)

    try:
        # Zip ko extract karein
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Us folder ko dhundhein jisme build.gradle hai
        project_dir = temp_dir
        for root, dirs, files in os.walk(temp_dir):
            if 'build.gradle' in files:
                project_dir = root
                break

        # Gradle command set karein (agar gradlew hai to use karein, warna system ka gradle)
        gradlew_path = os.path.join(project_dir, 'gradlew')
        if os.path.exists(gradlew_path):
            os.chmod(gradlew_path, 0o755) # Execute permission dein
            cmd = ['./gradlew', 'build']
        else:
            cmd = ['gradle', 'build']

        # Build process run karein
        process = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True)

        if process.returncode != 0:
            error_log = process.stderr if process.stderr else process.stdout
            return jsonify({'error': 'Build fail ho gaya.', 'log': error_log}), 500

        # Build folder me se .jar file dhundhein
        libs_dir = os.path.join(project_dir, 'build', 'libs')
        if not os.path.exists(libs_dir):
            return jsonify({'error': 'Build success hua par build/libs folder nahi mila.'}), 500

        jars = [f for f in os.listdir(libs_dir) if f.endswith('.jar')]
        if not jars:
            return jsonify({'error': 'Build ke baad koi .jar file nahi mili.'}), 500

        # Pehli mili hui jar file ko memory me load karein
        jar_path = os.path.join(libs_dir, jars[0])
        return_data = io.BytesIO()
        with open(jar_path, 'rb') as fo:
            return_data.write(fo.read())
        return_data.seek(0)
        jar_filename = jars[0]

        # Cleanup: Temp directory ko delete karein taki storage full na ho
        shutil.rmtree(temp_dir)

        # File client ko bhej dein
        return send_file(return_data, as_attachment=True, download_name=jar_filename, mimetype='application/java-archive')

    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 0.0.0.0 par run karein taki network me access ho sake
    app.run(host='0.0.0.0', port=5000, debug=True)
      
