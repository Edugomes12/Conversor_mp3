import streamlit as st
import subprocess
import os
import shutil
import zipfile
import tempfile
from pathlib import Path

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def check_ffmpeg():
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def convert_mp4_to_mp3(input_path: Path, output_path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-vn",
                "-acodec", "libmp3lame",
                "-ab", "192k",
                "-ar", "44100",
                str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip().split("\n")[-1]}

        if not output_path.exists() or output_path.stat().st_size == 0:
            return {"success": False, "error": "Arquivo de saída vazio ou não criado."}

        return {"success": True}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout: conversão demorou mais de 5 minutos."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_zip(mp3_files: list[Path]) -> Path:
    zip_path = OUTPUT_DIR / "todos_mp3.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in mp3_files:
            zf.write(f, f.name)
    return zip_path


def validate_file(uploaded_file) -> tuple[bool, str]:
    if not uploaded_file.name.lower().endswith(".mp4"):
        return False, f"'{uploaded_file.name}' não é um arquivo .mp4"

    if uploaded_file.size == 0:
        return False, f"'{uploaded_file.name}' está vazio"

    if uploaded_file.size > 500 * 1024 * 1024:
        return False, f"'{uploaded_file.name}' excede 500 MB"

    return True, ""


st.set_page_config(page_title="MP4 → MP3 Converter", page_icon="🎵", layout="centered")

st.title("🎵 Conversor MP4 → MP3")
st.caption("Faça upload de vídeos .mp4 e converta para .mp3 em lote.")

if not check_ffmpeg():
    st.error(
        "⚠️ **ffmpeg não encontrado!**\n\n"
        "Instale o ffmpeg no seu sistema:\n"
        "- **Ubuntu/Debian:** `sudo apt install ffmpeg`\n"
        "- **Mac:** `brew install ffmpeg`\n"
        "- **Windows:** baixe em https://ffmpeg.org/download.html\n\n"
        "No **Streamlit Cloud**, adicione um arquivo `packages.txt` com `ffmpeg` dentro."
    )
    st.stop()

uploaded_files = st.file_uploader(
    "Selecione os arquivos .mp4",
    type=["mp4"],
    accept_multiple_files=True
)

if uploaded_files:
    valid_files = []
    invalid_files = []

    for f in uploaded_files:
        is_valid, reason = validate_file(f)
        if is_valid:
            valid_files.append(f)
        else:
            invalid_files.append(reason)

    col1, col2 = st.columns(2)
    col1.metric("📁 Arquivos válidos", len(valid_files))
    col2.metric("❌ Inválidos", len(invalid_files))

    if invalid_files:
        with st.expander("Ver erros de validação"):
            for msg in invalid_files:
                st.warning(msg)

    if valid_files:
        st.divider()
        st.subheader("📋 Fila de conversão")
        for i, f in enumerate(valid_files, 1):
            size_mb = f.size / (1024 * 1024)
            st.text(f"  {i}. {f.name} ({size_mb:.1f} MB)")

        if st.button("🚀 Converter todos", type="primary", use_container_width=True):
            for old in OUTPUT_DIR.glob("*.mp3"):
                old.unlink()
            zip_old = OUTPUT_DIR / "todos_mp3.zip"
            if zip_old.exists():
                zip_old.unlink()

            converted_files: list[Path] = []
            errors: list[str] = []

            progress_bar = st.progress(0, text="Iniciando conversão...")
            status_container = st.empty()

            for idx, uploaded in enumerate(valid_files):
                progress = idx / len(valid_files)
                progress_bar.progress(progress, text=f"Convertendo {idx + 1}/{len(valid_files)}: {uploaded.name}")
                status_container.info(f"⏳ Processando: **{uploaded.name}**")

                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp.write(uploaded.getbuffer())
                    tmp_path = Path(tmp.name)

                mp3_name = Path(uploaded.name).stem + ".mp3"
                output_path = OUTPUT_DIR / mp3_name

                result = convert_mp4_to_mp3(tmp_path, output_path)

                tmp_path.unlink(missing_ok=True)

                if result["success"]:
                    converted_files.append(output_path)
                else:
                    errors.append(f"{uploaded.name}: {result['error']}")

            progress_bar.progress(1.0, text="Conversão finalizada!")
            status_container.empty()

            st.divider()

            if converted_files:
                st.success(f"✅ {len(converted_files)}/{len(valid_files)} arquivo(s) convertido(s) com sucesso!")

                st.subheader("⬇️ Downloads individuais")
                for mp3_path in converted_files:
                    file_bytes = mp3_path.read_bytes()
                    size_mb = len(file_bytes) / (1024 * 1024)
                    st.download_button(
                        label=f"🎶 {mp3_path.name} ({size_mb:.1f} MB)",
                        data=file_bytes,
                        file_name=mp3_path.name,
                        mime="audio/mpeg",
                        use_container_width=True
                    )

                if len(converted_files) > 1:
                    st.subheader("📦 Download ZIP (todos)")
                    zip_path = create_zip(converted_files)
                    zip_bytes = zip_path.read_bytes()
                    zip_size_mb = len(zip_bytes) / (1024 * 1024)
                    st.download_button(
                        label=f"📦 Baixar todos ({zip_size_mb:.1f} MB)",
                        data=zip_bytes,
                        file_name="todos_mp3.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

            if errors:
                st.subheader("⚠️ Erros na conversão")
                for err in errors:
                    st.error(err)

else:
    st.info("👆 Faça upload de um ou mais arquivos .mp4 para começar.")
