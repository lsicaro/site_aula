from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///aulas.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Modelos do Banco de Dados
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)  # Senha armazenada como hash
    role = db.Column(db.String(50), nullable=False)  # 'aluno' ou 'professora'

class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hourly_rate = db.Column(db.Float, nullable=False, default=50.0)

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    student_email = db.Column(db.String(100), nullable=False)
    appointment_date = db.Column(db.String(50), nullable=False)  # Data da aula
    start_time = db.Column(db.String(5), nullable=False)  # Formato HH:MM
    end_time = db.Column(db.String(5), nullable=False)    # Formato HH:MM
    hours = db.Column(db.Float, nullable=False)           # Calculado
    total = db.Column(db.Float, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Cria as tabelas (caso não existam)
def create_tables():
    db.create_all()
    if not Config.query.first():
        config = Config(hourly_rate=50.0)
        db.session.add(config)
        db.session.commit()

# Rota Home: página inicial com opções de login e cadastros
@app.route('/')
def home():
    return render_template('home.html')

# Cadastro de Aluno
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name']
        email    = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash("Email já cadastrado.", "danger")
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(name=name, email=email, password=hashed_password, role='aluno')
        db.session.add(new_user)
        db.session.commit()
        flash("Cadastro realizado com sucesso! Faça login para continuar.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

# Cadastro de Professor com verificação de código de acesso
@app.route('/register_teacher', methods=['GET', 'POST'])
def register_teacher():
    if request.method == 'POST':
        name         = request.form['name']
        email        = request.form['email']
        password     = request.form['password']
        teacher_code = request.form['teacher_code']
        if teacher_code != "adminprofessor":
            flash("Código de acesso para professor inválido.", "danger")
            return redirect(url_for('register_teacher'))
        if User.query.filter_by(email=email).first():
            flash("Email já cadastrado.", "danger")
            return redirect(url_for('register_teacher'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_teacher = User(name=name, email=email, password=hashed_password, role='professora')
        db.session.add(new_teacher)
        db.session.commit()
        flash("Cadastro realizado com sucesso! Faça login para continuar.", "success")
        return redirect(url_for('login'))
    return render_template('register_teacher.html')

# Login (único para alunos e professores)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login efetuado com sucesso!", "success")
            if user.role == 'professora':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('booking'))
        else:
            flash("Email ou senha incorretos.", "danger")
    return render_template('login.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Você saiu da conta.", "info")
    return redirect(url_for('home'))

# Agendamento de Aula (para alunos)
@app.route('/booking', methods=['GET', 'POST'])
@login_required
def booking():
    if current_user.role != 'aluno':
        flash("Somente alunos podem agendar aulas.", "danger")
        return redirect(url_for('home'))
    config = Config.query.first()
    teachers = User.query.filter_by(role='professora').all()
    if request.method == 'POST':
        student_name  = request.form['name']
        student_email = request.form['email']
        appointment_date = request.form['date']
        start_time = request.form['start_time']  # Formato HH:MM
        end_time = request.form['end_time']      # Formato HH:MM

        try:
            start_dt = datetime.strptime(start_time, '%H:%M')
            end_dt = datetime.strptime(end_time, '%H:%M')
            delta = (end_dt - start_dt).total_seconds() / 3600.0
            if delta <= 0:
                flash("O horário final deve ser posterior ao horário inicial.", "danger")
                return redirect(url_for('booking'))
        except Exception as e:
            flash("Formato de horário inválido.", "danger")
            return redirect(url_for('booking'))

        teacher_id = int(request.form['teacher_id'])
        total = config.hourly_rate * delta

        new_appointment = Appointment(
            student_id=current_user.id,
            teacher_id=teacher_id,
            student_name=student_name,
            student_email=student_email,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            hours=delta,
            total=total
        )
        db.session.add(new_appointment)
        db.session.commit()
        flash(f'Aula agendada com sucesso! Valor total: R$ {total:.2f}', 'success')
        return redirect(url_for('booking'))
    appointments = Appointment.query.filter_by(student_id=current_user.id).all()
    return render_template('booking.html', config=config, teachers=teachers, appointments=appointments)

# Painel Administrativo (para professores)
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'professora':
        flash("Acesso negado.", "danger")
        return redirect(url_for('home'))
    config = Config.query.first()
    appointments = Appointment.query.filter_by(teacher_id=current_user.id).all()
    return render_template('admin.html', config=config, appointments=appointments)

# Atualizar o valor da hora (apenas para professores)
@app.route('/admin/update_rate', methods=['POST'])
@login_required
def update_rate():
    if current_user.role != 'professora':
        flash("Acesso negado.", "danger")
        return redirect(url_for('home'))
    new_rate = request.form['hourly_rate']
    try:
        new_rate = float(new_rate)
        config = Config.query.first()
        config.hourly_rate = new_rate
        db.session.commit()
        flash("Valor da hora atualizado com sucesso!", "success")
    except ValueError:
        flash("Por favor, insira um valor numérico válido.", "danger")
    return redirect(url_for('admin'))

# Cancelar agendamento (aluno ou professor, somente o seu)
@app.route('/cancel/<int:id>')
@login_required
def cancel(id):
    appointment = Appointment.query.get_or_404(id)
    if current_user.role == 'aluno' and appointment.student_id != current_user.id:
        flash("Você não pode cancelar esta aula.", "danger")
        return redirect(url_for('booking'))
    if current_user.role == 'professora' and appointment.teacher_id != current_user.id:
        flash("Você não pode cancelar esta aula.", "danger")
        return redirect(url_for('admin'))
    db.session.delete(appointment)
    db.session.commit()
    flash("Aula cancelada com sucesso.", "info")
    if current_user.role == 'professora':
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('booking'))

if __name__ == '__main__':
    with app.app_context():
        create_tables()
    app.run(debug=True)
