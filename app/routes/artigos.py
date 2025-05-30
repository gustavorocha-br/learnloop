# Importação dos módulos e classes necessárias
from flask import render_template, redirect, session, jsonify, request, make_response, send_file
from app.routes import artigos_bp
from app.models import Artigo, User, buscas
from app import db
from passlib.hash import bcrypt_sha256
import uuid
import markdown
import os
from docx import Document
from sqlalchemy import desc
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
if azure_endpoint is None:
    raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set.")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
    api_version="2024-07-01-preview",
    azure_endpoint=azure_endpoint
)

@artigos_bp.route("/")
def homepage():
    try:
        user = session.get('user', 'Visitante')
        if user != 'Visitante':
            user_db = User.query.filter_by(id=user).first()
        else:
            user_db = None
        ultimos_artigos = Artigo.query.order_by(desc(Artigo.likes)).limit(4).all()
        return render_template("index.html", user=user_db, artigos=ultimos_artigos)
    except:
        return render_template("index.html")

from datetime import datetime

@artigos_bp.route("/create-artigo", methods=["POST", "GET"])
def criarArtigo():
    if request.method == "POST":
        title = request.form["title-art"]
        conteudo = request.form["conteudo-art"]
        categoria = request.form["category"]
        tags = request.form["tags"]
    
        if title == "" or title == " " or len(conteudo) < 1:
            return "Digite algo válido!"

        try:
            user = session["user"]
        except:
            user = "visit"

        if user == "visit":
            return "Você precisa estar logado."

        # Captura a data e hora atuais e formata para o padrão do sitemap.xml
        data = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00')

        newArtigo = Artigo(
            titulo=title, 
            texto=markdown.markdown(conteudo), 
            autor=user, 
            data=data,  # Salvando a data formatada
            categoria=categoria, 
            tags=tags, 
            likes=0, 
            id=str(uuid.uuid4()), 
            views=0
        )
        db.session.add(newArtigo)
        db.session.commit()

        return redirect("/artigo/" + newArtigo.id)

    try:
        user = session['user']
    except:
        return redirect("/login")

    return render_template("create-artigo.html")

# Rota para excluir um artigo
@artigos_bp.route("/delete-artigo/<id>", methods=["GET"])
def deleteArtigo(id):
    artigo = Artigo.query.filter_by(id=id).first()
    if not artigo:
        return "Artigo Não Existe"
    user = User.query.filter_by(id=artigo.autor).first()

    if artigo:
        senha = request.args.get("senha")

        if bcrypt_sha256.verify(senha, user.password):
            db.session.delete(artigo)
            db.session.commit()
            return jsonify({"msg": "success"})
        else:
            return redirect("/artigo/"+artigo.id)
    else:
        return "Artigo Não Existe"

@artigos_bp.route("/delete-artigo/<id>/admin", methods=["GET"])
def deleteArtigoAdm(id):
    artigo = Artigo.query.filter_by(id=id).first()
    db.session.delete(artigo)
    db.session.commit()
    return 'ok'

@artigos_bp.route("/add-like/<id>")
def likePost(id):
    artigo = Artigo.query.filter_by(id=id).first()
    artigo.likes = artigo.likes + 1
    db.session.commit()
    return redirect("/artigo/"+id)

@artigos_bp.route("/delete-like/<id>")
def deslikePost(id):
    artigo = Artigo.query.filter_by(id=id).first()
    artigo.likes = artigo.likes - 1
    db.session.commit()
    return redirect("/artigo/"+id)

@artigos_bp.route("/artigo/<id>")
def artigoPage(id):
    try:
        user = session['user']
    except:
        user = 'visit'

    artigo = Artigo.query.filter_by(id=id).first()
    artigo.views = artigo.views + 1
    
    db.session.commit()
    autor = User.query.filter_by(id=artigo.autor).first()
    if artigo:
        return render_template("post.html", artigo=artigo, autor=autor)
    else:
        return "<h1>Artigo Não Existe</h1"

@artigos_bp.route("/search")
def pageSearch():
    categorias = Artigo.query.with_entities(Artigo.categoria).distinct().all()
    nomesCategorias = [categoria[0] for categoria in categorias]
    return render_template("search.html", categorys=nomesCategorias)

@artigos_bp.route("/search/category/<categoria>")
def buscar_artigo_categoria(categoria):
    artigos = Artigo.query.filter_by(categoria=categoria).all()

    if artigos:
        return jsonify(artigos)
    else:
        response = make_response(jsonify({"message": "Nenhum artigo encontrado para esta categoria"}), 404)
        return response

def search_word_files(directory, search_terms):
    results = set()

    for filename in os.listdir(directory):
        if filename.endswith(".docx"):
            file_path = os.path.join(directory, filename)
            document = Document(file_path)

            for paragraph in document.paragraphs:
                for run in paragraph.runs:
                    text = run.text
                    for term in search_terms:
                        if term.lower() in text.lower():
                            results.add(filename)

    return [{"file_name": filename} for filename in results]

@artigos_bp.route("/search/artigos")
def artigosSearch():
    pesquisa_i = request.args.get("pesquisa")
    pesquisa = pesquisa_i.lower()

    try:
        user = session["user"]
    except:
        user = "visit"
    newBsc = buscas(user=user, termo=pesquisa)
    db.session.add(newBsc)
    db.session.commit()

    artigos = Artigo.query.filter(
        (Artigo.titulo.ilike(f"%{pesquisa}%")) |
        (Artigo.autor.ilike(f"%{pesquisa}%")) |
        (Artigo.categoria.ilike(f"%{pesquisa}%")) |
        (Artigo.data.ilike(f"%{pesquisa}%")) |
        (Artigo.tags.ilike(f"%{pesquisa}%"))
    ).all()

    directory_path = "app/static/feciba"
    search_terms = pesquisa_i.split(" ")
    word_search_results = search_word_files(directory_path, search_terms)

    return render_template("feed.html", artigos=artigos, feciba_results=word_search_results)

@artigos_bp.route("/download-file/<filename>")
def download_file(filename):
    directory_path = os.path.abspath("app/static/feciba")
    file_path = os.path.join(directory_path, filename)

    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "Arquivo não encontrado", 404

@artigos_bp.route("/feed/projetos-feciba")
def feed_projetos_feciba():
    directory_path = "app/static/feciba"
    projetos_feciba = [{"file_name": filename} for filename in os.listdir(directory_path) if filename.endswith(".docx")]
    return render_template("feed.html", artigos=None, feciba_results=projetos_feciba)

@artigos_bp.route("/feed/artigos")
def feed_artigos():
    artigos = Artigo.query.all()
    return render_template("feed.html", artigos=artigos, feciba_results=None)



@artigos_bp.route("/api/gerar-artigo-ai", methods=["POST"])
def gerarArtigoPorIa():
    try:
        user = session['user']
        userDb = User.query.filter_by(id=user).first()
        if userDb:
            data = request.get_json()


            # Fazendo a chamada à API do Azure OpenAI
            chat_completion = client.chat.completions.create(
                model="gpt-4o",  # Nome do deployment configurado no Azure
                messages=[
                    {"role": "system", "content": "Você gera artigos autônomos longos e bem estruturados, com base na entrada do usuário, com linguagem informal e atraente."},
                    {"role": "user", "content": f"Resumo: {data['resumo']}"}
                ]
            )

            assistant_response = chat_completion.choices[0].message.content

            return jsonify({
                "msg": "success",
                "response": assistant_response
            })
    except Exception as e:
        return jsonify({"msg": f"Erro: {e}"})

@artigos_bp.route("/api/tirar-duvida-artigo", methods=["POST"])
def tiraDuvidaArtigo():
    try:  
        data = request.get_json()
        user_message = f"Artigo: {data['conteudo_artigo']}. Dúvida: {data['duvida']}"


        # Fazendo a chamada à API do Azure OpenAI
        chat_completion = client.chat.completions.create(
            model="gpt-4o",  # Nome do deployment configurado no Azure
            messages=[
                {"role": "system", "content": "Você responde dúvidas sobre o conteúdo de artigos de forma clara e direta."},
                {"role": "user", "content": user_message}
            ]
        )

        assistant_response = chat_completion.choices[0].message.content


        return jsonify({
            "msg": "success",
            "resposta": assistant_response
        })
    except Exception as e:
        return jsonify({"msg": f"Houve um erro: {e}"})

from PIL import Image
import base64
import io

def image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

@artigos_bp.route("/api/carregar-redacao", methods=["POST"])
def carregar_redacao():
    try:
        if 'foto' not in request.files or not request.files['foto'].filename:
            return jsonify({"msg": "Nenhum arquivo enviado"}), 400

        foto = request.files['foto']
        filename = foto.filename
        image_path = os.path.join('/tmp', filename)
        foto.save(image_path)

        img_base64 = image_to_base64(image_path)

        chat_completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Transcreva apenas o texto da redação manuscrita da imagem enviada, sem comentários, explicações ou introduções. Retorne somente o texto."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Transcreva o texto da imagem."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ]
        )

        texto_extraido = chat_completion.choices[0].message.content.strip()

        return jsonify({"msg": "success", "redacao": texto_extraido})

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"msg": "error", "error": str(e)}), 500

    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

@artigos_bp.route("/api/gerar-artigo", methods=["POST"])
def gerar_artigo():
    try:
        if 'foto' not in request.files or not request.files['foto'].filename:
            return jsonify({"msg": "Nenhum arquivo enviado"}), 400

        foto = request.files['foto']
        filename = foto.filename
        image_path = os.path.join('/tmp', filename)
        foto.save(image_path)

        img_base64 = image_to_base64(image_path)

        chat_completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Gere apenas o artigo completo, estruturado e informal, a partir do conteúdo manuscrito da imagem enviada. Não inclua comentários, explicações ou introduções. Retorne somente o artigo. Não deixe referências a imagem, ou seja, apenas o conteúdo do artigo, faz de conta que nem te enviaram uma imagem."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Gere o artigo a partir do texto manuscrito da imagem."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ]
        )

        content = chat_completion.choices[0].message.content
        texto_extraido = content.strip() if content else ""

        return jsonify({"msg": "success", "artigo": texto_extraido})

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"msg": "error", "error": str(e)}), 500

    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

