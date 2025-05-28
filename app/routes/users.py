from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for, make_response, Response
from app import db
from app.models import User, Artigo, Redacao, Correcoes
from passlib.hash import bcrypt_sha256
import uuid
import markdown
from app.routes import users_bp

# Função de criptografia de senha
def crip(dado):
    dado_criptografado = bcrypt_sha256.hash(dado)
    return str(dado_criptografado)

# Rota para o cadastro de um novo usuário via API
@users_bp.route('/api/signup', methods=["POST"])
def signup():
    username = request.form["username"]
    password = crip(request.form["password"])
    email = request.form["email"]

    newUser = User(username=username, email=email, password=password, id=str(uuid.uuid4()))
    db.session.add(newUser)
    db.session.commit()
    session["user"] = newUser.id
    session.permanent = True

    return redirect("/")

# Rota de login de usuário via API
@users_bp.route("/api/login", methods=["GET"])
def login():
    username = request.args.get("username")
    password = request.args.get("password")
    user = User.query.filter_by(username=username).first()
    if user and bcrypt_sha256.verify(password, user.password):
        session["user"] = user.id
        session.permanent = True

        return redirect("/")
    else:
        return "<h1>Usuário ou senha incorretos</h1>"

# Rota para logout
@users_bp.route("/api/logout")
def logout():
    session.clear()
    return redirect("/login")

# Rota para obter informações do usuário logado
@users_bp.route("/api/user")
def user():
    user_id = session.get("user")
    user = User.query.filter_by(id=user_id).first()
    return jsonify({"user": user})

# Rota para excluir o usuário
@users_bp.route("/api/delete-user", methods=["POST"])
def delete_user():
    user_id = session.get("user")
    user = User.query.filter_by(id=user_id).first()
    senha = request.get_json()["senha"]
    if bcrypt_sha256.verify(senha, user.password):
        db.session.delete(user)
        db.session.commit()
        session.clear()
        return jsonify({"msg": "usuário deletado com sucesso"})
    else:
        return jsonify({"msg": "Senha incorreta"})

# Rota para atualizar os dados do usuário
@users_bp.route("/api/update-user", methods=["POST"])
def update_user():
    data = request.get_json()
    user_id = session.get("user")
    user = User.query.filter_by(id=user_id).first()
    user.username = data["username"]
    user.password = data["password"]
    db.session.commit()
    return jsonify({"msg": "usuário atualizado com sucesso"})


