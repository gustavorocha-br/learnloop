# Importação dos módulos e classes necessárias
from flask import render_template, redirect, session, jsonify, request, make_response, send_file
from app.routes import artigos_bp
from app.models import Artigo, User, buscas, Redacao
from app import db
from passlib.hash import bcrypt_sha256
import uuid
import markdown
import os
from docx import Document
from sqlalchemy import desc
import google.generativeai as genai

@artigos_bp.route("/")
def homepage():
    try:
        user = session.get('user', 'Visitante')
        if user != 'Visitante':
            user_db = User.query.filter_by(id=user).first()
        else:
            user_db = None
        ultimos_artigos = Artigo.query.order_by(desc(Artigo.likes)).limit(12).all()
        return render_template("index.html", user=user_db, artigos=ultimos_artigos)
    except:
        return render_template("index.html")


@artigos_bp.route("/avaliar-redacao")
def redacion():
    try:
        user = session["user"]
        redacoes = Redacao.query.filter_by(user=user).all()
        return render_template("treino-redacao.html", redacoes=redacoes)
    except Exception as e:
        return redirect("/login")

# Rota para criar um artigo (pode ser acessada via POST ou GET)
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

        data = "sla"

        newArtigo = Artigo(titulo=title, texto=markdown.markdown(conteudo), autor=user, data=data, categoria=categoria, tags=tags, likes=0, id=str(uuid.uuid4()))
        db.session.add(newArtigo)
        db.session.commit()

        return redirect("/artigo/"+newArtigo.id)

    try:
        user = session['user']
    except:
        return redirect("/login")

    return render_template("create-artigo.html")

# Rota para excluir um artigo
@artigos_bp.route("/delete-artigo/<id>", methods=["GET"])
def deleteArtigo(id):
    artigo = Artigo.query.filter_by(id=id).first()
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

@artigos_bp.route("/learn-ai/redacao", methods=["POST"])
def gerarAvaliacaoPorIa():
    try:
        data = request.get_json()
        print(data["nivel"])
        genai.configure(api_key=os.environ["API_KEY"])
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction=f"Você é uma IA que avalia redações, foque nas informações do usuário, e forneça insights com base em redações nota mil no ENEM. Corrija com base nas competências do ENEM e atribua notas, e seja gentil e elogie bastante para motivar o estudante a continuar aprimorando. O nível de conhecimento dos usuários é: {data['nivel']}"
        )
        response = model.generate_content(f"Titulo: {data['title']}. Redação: {data['content']}")

        assistant_response = str(response.text)

        return jsonify({
            "msg": "success",
            "response": markdown.markdown(assistant_response)
        })
    except KeyError:
        return redirect('/login')

@artigos_bp.route("/api/gerar-artigo-ai", methods=["POST"])
def gerarArtigoPorIa():
    try:
        user = session['user']
        userDb = User.query.filter_by(id=user).first()
        if userDb:
            data = request.get_json()
            genai.configure(api_key=os.environ["API_KEY"])
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction="Como a IA Learn.Ai, você gera artigos autônomos longos e bem estruturados, com base na entrada do usuário. Os artigos devem ser descontraídos e autênticos, permitindo referências externas de forma moderada e uma linguagem informal. Acrescente informações relevantes para evitar superficialidade, com orientação para estudantes do Ensino Médio. Use emojis de forma atrativa e incentive os leitores a clicar no botão 'Tirar Dúvida' em caso de questionamentos, não coloque título nem subtítulo nenhum, apenas negrito, emojis etc."
            )
            response = model.generate_content(f"Resumo: {data['resumo']}")

            assistant_response = response.text
            return jsonify({
                "msg": "success",
                "response": assistant_response
            })
    except Exception as e:
        return print(f"Erro: {e}")

@artigos_bp.route("/quiz")
def quizPage():
    return render_template("quiz.html")

@artigos_bp.route("/gerar/quiz", methods=["POST"])
def gerarQuizPorIa():
    try:
        user = session.get('user')
        if user is None:
            return jsonify({"msg": "error", "error": "Usuário não autenticado"}), 401

        userDb = User.query.filter_by(id=user).first()
        if userDb is None:
            return jsonify({"msg": "error", "error": "Usuário não encontrado"}), 404

        data = request.get_json()
        genai.configure(api_key=os.environ["API_KEY"])
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction="Você é uma Inteligência Artificial que gera 1 pergunta de acordo com algum resumo que o usuário enviar, se não for um resumo, o usuário enviará apenas o assunto que ele tem dificuldade, e você vai gerar um quiz básico sobre o assunto. Crie com uma linguagem descontraída e autêntica, sem referências a outros sites, blogs, ou artigos já publicados."
        )
        response = model.generate_content(f"O que o usuário tem dificuldade: {data['dificuldades']}")

        assistant_response = response.text

        return jsonify({
            "msg": "success",
            "response": assistant_response
        })
    except Exception as e:
        return print(e)

@artigos_bp.route("/corrigir/quiz", methods=["POST"])
def corrigeQuizPorIa():
    try:
        user = session['user']
        userDb = User.query.filter_by(id=user).first()
        if user:
            data = request.get_json()
            genai.configure(api_key=os.environ["API_KEY"])
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction="Você é uma Inteligência Artificial que faz a correção de um quiz com perguntas e respostas que o usuário enviar, você vai explicar onde o usuário errou ou acertou, e vai dar dicas de como acertar na próxima, corrija de forma descontraída e leve."
            )
            response = model.generate_content(f"Questões: {data['perguntas']}. Respostas do usuário: {data['respostas']}")

            assistant_response = response.text
            print(assistant_response)
            return jsonify({
                "msg": "success",
                "response": assistant_response
            })
    except Exception as e:
        return redirect(f'Erro: {str(e)}')


@artigos_bp.route('/api/tirar-duvida-artigo', methods=["POST"])
def tiraDuvidaArtigo():
    try:  
        data = request.get_json()
        user_message = f"Artigo: {data['conteudo_artigo']}. Dúvida: {data['duvida']}"

        genai.configure(api_key=os.environ["API_KEY"])
        model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction="Você é uma Inteligência Artificial, que tira dúvida de um artigo. Você pode usar a base do artigo ou pegar outras referências. O importante é o usuário entender de vez o assunto. Responda de forma descontraída e não deixe o usuário fugir muito do artigo."
            )
        response = model.generate_content(user_message)

        assistant_response = response.text
        print(assistant_response)
        return jsonify({
                "msg": "success",
                "resposta": assistant_response
            })
    except Exception as e:
        return print(f"Houve um erro: {str(e)}")

from PIL import Image  # Adicionado

@artigos_bp.route("/api/carregar-redacao", methods=["POST"])
def carregar_redacao():
    try:
        # Verificar se o arquivo foi enviado
        if 'foto' not in request.files or not request.files['foto'].filename:
            return jsonify({"msg": "Nenhum arquivo enviado"}), 400

        foto = request.files['foto']
        filename = foto.filename
        print(filename)
        # Gerar um caminho seguro para a imagem temporária
        image_path = os.path.join('/tmp', filename)

        # Salvar a imagem temporariamente
        foto.save(image_path)

        # Configurar a API do Gemini
        genai.configure(api_key=os.environ["API_KEY"])
        img = Image.open(image_path)

        # Utilizar o modelo Gemini para extrair o texto
        model = genai.GenerativeModel(model_name="gemini-1.5-pro",
                                     system_instruction="Você é uma Inteligência Artificial que digitaliza redações manuscritas que o usuário enviar.")
        response = model.generate_content(["Digitalize a redação manuscrita pelo usuário.", img])

        # Obter o texto da resposta
        texto_extraido = response.text

        # Retornar o texto extraído
        return jsonify({"msg": "success", "redacao": texto_extraido})

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"msg": "error", "error": str(e)}), 500

    finally:
        # Remover a imagem temporária
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

        genai.configure(api_key=os.environ["API_KEY"])
        img = Image.open(image_path)

        model = genai.GenerativeModel(model_name="gemini-1.5-pro")
        response = model.generate_content(["Como a IA Learn.Ai, você gera artigos autônomos longos e bem estruturados, com base no conteúdo do caderno do usuário no qual ele enviou imagem. Os artigos devem ser descontraídos e autênticos, permitindo referências externas de forma moderada e uma linguagem informal. Acrescente informações relevantes para evitar superficialidade, com orientação para estudantes do Ensino Médio. Use emojis de forma atrativa e incentive os leitores a clicar no botão 'Tirar Dúvida' em caso de questionamentos.", img])

        texto_extraido = response.text

        # Supondo que o modelo gere um artigo baseado no conteúdo extraído
        

        
        return jsonify({"msg": "success", "artigo": texto_extraido})

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"msg": "error", "error": str(e)}), 500

    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

