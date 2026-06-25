from flask import Flask, render_template, request, redirect, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import calendar


app = Flask(__name__)


import os

app.config["SECRET_KEY"] = "smartparking123"

db_dir = os.path.join(os.path.dirname(__file__), "instance")
os.makedirs(db_dir, exist_ok=True)

db_path = os.path.join(db_dir, "database.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==================================
# MODELO USUÁRIO
# ==================================

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    usuario = db.Column(db.String(50), unique=True)
    email = db.Column(db.String(100))
    senha = db.Column(db.String(255))

# ==================================
# MODELO VEÍCULO
# ==================================

class Veiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proprietario = db.Column(db.String(100))
    placa = db.Column(db.String(20))
    tipo = db.Column(db.String(50))
    vaga = db.Column(db.String(10))
    entrada = db.Column(db.String(50))
    saida = db.Column(db.String(50))
    valor = db.Column(db.Float, default=0)
    pago = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)

# ==================================
# LOGIN
# ==================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        senha = request.form["senha"]

        user = Usuario.query.filter_by(
            usuario=usuario
        ).first()

        if user and check_password_hash(user.senha, senha):
            session["usuario"] = user.usuario
            return redirect("/dashboard")

        flash("Usuário ou senha inválidos")

    return render_template("login.html")

# ==================================
# CADASTRO DE USUÁRIO
# ==================================

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":

        novo_usuario = Usuario(
            nome=request.form["nome"],
            usuario=request.form["usuario"],
            email=request.form["email"],
            senha=generate_password_hash(
                request.form["senha"]
            )
        )

        db.session.add(novo_usuario)
        db.session.commit()

        flash("Cadastro realizado com sucesso!")
        return redirect("/")

    return render_template("cadastro.html")

# ==================================
# DASHBOARD
# ==================================

@app.route("/dashboard")
def dashboard():

    if "usuario" not in session:
        return redirect("/")

    veiculos = Veiculo.query.filter_by(
        ativo=True
    ).all()

    ocupadas = len(veiculos)
    livres = 30 - ocupadas

    # Receita total (todas as entradas/saídas registradas)
    receita = sum(
        v.valor for v in Veiculo.query.all()
    )

    # Receita do mês atual vs mês passado (considera v.entrada)
    now = datetime.now()
    ano_atual, mes_atual = now.year, now.month
    if mes_atual == 1:
        mes_passado = 12
        ano_passado = ano_atual - 1
    else:
        mes_passado = mes_atual - 1
        ano_passado = ano_atual

    rendimento_mes = 0.0
    rendimento_mes_passado = 0.0

    for v in veiculos:
        if not v.entrada:
            continue
        try:
            dt = datetime.strptime(v.entrada, "%d/%m/%Y %H:%M")
        except ValueError:
            continue

        y, m = dt.year, dt.month
        valor = float(v.valor or 0)

        if y == ano_atual and m == mes_atual:
            rendimento_mes += valor
        if y == ano_passado and m == mes_passado:
            rendimento_mes_passado += valor

    perc_mudanca = None
    if rendimento_mes_passado and rendimento_mes_passado != 0:
        perc_mudanca = ((rendimento_mes - rendimento_mes_passado) / rendimento_mes_passado) * 100

    return render_template(
        "dashboard.html",
        veiculos=veiculos,
        ocupadas=ocupadas,
        livres=livres,
        receita=receita,
        rendimento_mes=rendimento_mes,
        rendimento_mes_passado=rendimento_mes_passado,
        perc_mudanca=perc_mudanca
    )

# ==================================
# CADASTRAR VEÍCULO
# ==================================

@app.route("/cadastrar_veiculo", methods=["POST"])
def cadastrar_veiculo():

    if "usuario" not in session:
        return redirect("/")

    nome = request.form["nome"]
    placa = request.form["placa"]
    tipo = request.form["tipo"]
    vaga = request.form["vaga"]

    existe = Veiculo.query.filter_by(
        vaga=vaga,
        ativo=True
    ).first()

    if existe:
        flash("Esta vaga já está ocupada!")
        return redirect("/dashboard")

    novo = Veiculo(
        proprietario=nome,
        placa=placa,
        tipo=tipo,
        vaga=vaga,
        entrada=datetime.now().strftime("%d/%m/%Y %H:%M"),
        ativo=True
    )

    db.session.add(novo)
    db.session.commit()

    return redirect("/dashboard")

# ==================================
# SAÍDA DE VEÍCULO
# ==================================

@app.route("/saida/<int:id>")
def saida(id):

    veiculo = Veiculo.query.get_or_404(id)

    veiculo.saida = datetime.now().strftime(
        "%d/%m/%Y %H:%M"
    )

    veiculo.valor = 10.00
    veiculo.pago = True
    veiculo.ativo = False

    db.session.commit()

    return redirect("/dashboard")

# ==================================
# HISTÓRICO
# ==================================

@app.route("/historico")
def historico():

    if "usuario" not in session:
        return redirect("/")

    veiculos = Veiculo.query.all()

    return render_template(
        "historico.html",
        veiculos=veiculos,
        dias_trabalhados=None,
        rendimento_total=0
    )


@app.route("/historico/limpar", methods=["POST"])
def historico_limpar():

    if "usuario" not in session:
        return redirect("/")

    # remove tudo do histórico (registros inativos)
    Veiculo.query.delete()
    db.session.commit()
    return redirect("/historico")


@app.route("/historico/relatorio", methods=["GET"])
def historico_relatorio():

    if "usuario" not in session:
        return redirect("/")

    veiculos = Veiculo.query.all()

    # Dias trabalhados (considera a data da ENTRADA)
    datas = set()
    rendimento_total = 0.0

    for v in veiculos:
        if v.entrada:
            # entrada vem em "%d/%m/%Y %H:%M"
            try:
                dt = datetime.strptime(v.entrada, "%d/%m/%Y %H:%M")
                datas.add(dt.date())
            except ValueError:
                pass

        if v.valor:
            rendimento_total += float(v.valor)

    dias_trabalhados = len(datas)

    return render_template(
        "historico.html",
        veiculos=veiculos,
        dias_trabalhados=dias_trabalhados,
        rendimento_total=rendimento_total
    )


# ==================================
# PERFIL
# ==================================

@app.route("/perfil")
def perfil():

    if "usuario" not in session:
        return redirect("/")

    total = Veiculo.query.count()

    ocupadas = Veiculo.query.filter_by(
        ativo=True
    ).count()

    livres = 30 - ocupadas

    receita = sum(
        v.valor for v in Veiculo.query.all()
    )

    return render_template(
        "perfil.html",
        total=total,
        ocupadas=ocupadas,
        livres=livres,
        receita=receita
    )

# ==================================
# LOGOUT
# ==================================

@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")

# ==================================
# CRIA BANCO AUTOMATICAMENTE
# ==================================

def _parse_dt_entrada(s: str):
    try:
        return datetime.strptime(s, "%d/%m/%Y %H:%M")
    except Exception:
        return None


def _mes_ano(d: datetime):
    return d.year, d.month


@app.route("/terminar_mes", methods=["GET"])
def terminar_mes():

    if "usuario" not in session:
        return redirect("/")

    now = datetime.now()
    ano_atual, mes_atual = now.year, now.month

    if mes_atual == 1:
        mes_passado = 12
        ano_passado = ano_atual - 1
    else:
        mes_passado = mes_atual - 1
        ano_passado = ano_atual

    carros = motos = suvs = caminhoes = 0
    carros_p = motos_p = suvs_p = caminhoes_p = 0

    rendimento_mes = 0.0
    rendimento_mes_passado = 0.0

    veiculos = Veiculo.query.all()

    for v in veiculos:
        if not v.entrada:
            continue
        dt = _parse_dt_entrada(v.entrada)
        if not dt:
            continue

        y, m = _mes_ano(dt)
        tipo = (v.tipo or "").strip()
        valor = float(v.valor or 0)

        if y == ano_atual and m == mes_atual:
            rendimento_mes += valor
            if tipo == "Carro":
                carros += 1
            elif tipo == "Moto":
                motos += 1
            elif tipo == "SUV":
                suvs += 1
            elif tipo == "Caminhão":
                caminhoes += 1

        if y == ano_passado and m == mes_passado:
            rendimento_mes_passado += valor
            if tipo == "Carro":
                carros_p += 1
            elif tipo == "Moto":
                motos_p += 1
            elif tipo == "SUV":
                suvs_p += 1
            elif tipo == "Caminhão":
                caminhoes_p += 1

    # variação % vs mês passado
    perc_mudanca = None
    if rendimento_mes_passado and rendimento_mes_passado != 0:
        perc_mudanca = ((rendimento_mes - rendimento_mes_passado) / rendimento_mes_passado) * 100

    mensagem = None
    if perc_mudanca is not None:
        if perc_mudanca >= 0:
            mensagem = f"Parabéns, vocês melhoraram {perc_mudanca:.2f}% comparado ao mês passado"
        else:
            mensagem = f"Vocês não Superaram {abs(perc_mudanca):.2f}% do Mês passado, mais não desanimem!"

    return render_template(
        "terminar_mes.html",
        mensagem=mensagem,
        carros=carros,
        motos=motos,
        suvs=suvs,
        caminhoes=caminhoes,
        rendimento_mes=rendimento_mes,
        rendimento_mes_passado=rendimento_mes_passado,
        perc_mudanca=round(perc_mudanca, 2) if perc_mudanca is not None else None,
        ano_atual=ano_atual,
        mes_atual=mes_atual,
    )


# ==================================
# CRIA BANCO AUTOMATICAMENTE
# ==================================

with app.app_context():
    db.create_all()

    # cria usuário admin caso não exista
    admin = Usuario.query.filter_by(
        usuario="admin"
    ).first()

    if not admin:
        admin = Usuario(
            nome="Administrador",
            usuario="admin",
            email="admin@smartparking.com",
            senha=generate_password_hash("123456")
        )

        db.session.add(admin)
        db.session.commit()

# ==================================
# INICIAR SERVIDOR
# ==================================

if __name__ == "__main__":
    app.run(debug=True)