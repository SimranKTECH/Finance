import os
import datetime
import sqlite3
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # to make sure you are loading the stocks of current user only
    # ex: if aswin is logging in, i only wanna see aswin ka stocks, not  of simran
    portfolios = db.execute("SELECT * from purchase where user_id = ?", session["user_id"])

    # a list of all the stocks this person owns
    # i am doing this so i know which stocks i have to look up
    list_of_stocks = []
    for portfolio in portfolios:
        if portfolio["stock"] not in list_of_stocks:
            list_of_stocks.append(portfolio["stock"])

    # now for each stock this person holds, we obviously want its current price and all
    # for which we need to lookup

    # stock data is a dict where key = stock symbol, value = "the dict returned by lookup function"
    stock_data = {}

    for stock in list_of_stocks:
        stock_data[stock] = lookup(stock)

    # calculate the total money this user has currently ie, number of stocks * current value of it
    total_money = 0
    for portfolio in portfolios:
        total_money += stock_data[portfolio['stock']]['price']*portfolio['stock_count']
        
    balance = 0
    bal = db.execute("SELECT cash from users where id = ?", session["user_id"])
    balance = float(bal[0]["cash"])
    balance = "{:.2f}".format(balance)

    
    # the idea was to, have one variable which has sql output, and another dictionary which basically
    # has the info about stocks which this person owns.

    # so while displaying, we can display the apt stock details for that row
    return render_template("index.html", portfolios=portfolios, stock_data=stock_data, total_money=total_money, balance = balance, fb = float(balance))
    return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        symbol = symbol.upper()

        # ensure the symbol place is not blank
        if not symbol:
            return apology("must provide symbol", 403)

        data_recieved = lookup(symbol)
        
        if not data_recieved:
            return apology("Invalid Symbol", 400)

        try:
            shares = float(shares)
        except ValueError:
            return apology("Not a valid integer", 400)
            
        if (int(shares) != shares) or (shares <= 0):
            return apology("Invalid shares", 400)
            
        # store the price information of the required stock
        latest_price = float(data_recieved["price"])

        # to see how much cash currently the user has
        money = db.execute("select cash, username from users where id = ?", session["user_id"])
        name = db.execute("select username from users where id = ?", session["user_id"])
        name = name[0]["username"]
        money = money[0]["cash"]

        money = float(money)
        
        
        user_id = session["user_id"]

        # if user sends invalid symb, then anyways we get None
        if data_recieved == None:
            # apology for incorrect symbol
            return apology("Invalid symbol")
        if shares < 0:
            return apology("shares should be a whole number", 400)

        print(type(shares), type(latest_price))
        total_cost = shares * latest_price

        if money < total_cost:
            return apology("Your account doesn't have required balance to buy this stock")

        else:
            # get the current datetime and store it in a variable
            currentDateTime = datetime.datetime.now()
            # make the database connection with detect_types
            
            stockexists = db.execute("select * from purchase where stock = ?", symbol)
            print(stockexists)
            if len(stockexists) == 0:
                print("inserting new")
                inserting = db.execute("insert into purchase(user_id, name, stock, price, time, stock_count) VALUES (?, ?, ?, ?, ?, ?)", user_id, name, symbol, total_cost, currentDateTime, shares)
            else:
                updatingold = db.execute("UPDATE purchase set stock_count = stock_count + ? where user_id = ?", shares, user_id)

            # step 1: record the transaction in the **purchase** table with all the necessary details.
            # attributes in purchase table : user_id, name, stock, price, time
            # how to insert row sqlite python
            # step 2: update the bank balance of the **user** in the users table
            # using the update query in sql if you remember lol
            updating = db.execute("UPDATE users set cash = cash - ? where id = ?", total_cost, user_id)
            insert_history = db.execute("insert into history(id, Symbol, Shares, Price, Transacted) VALUES (?, ?, ?, ?, ?)", user_id, symbol, shares, latest_price, currentDateTime)
        return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    portfolios = db.execute("SELECT Symbol, Shares, Price, Transacted from history where id = ?", session["user_id"])
    
    return render_template("history.html", portfolios=portfolios)
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # user reached route via POST
    if request.method == "POST":
        symbol = request.form.get("symbol")

        data_recieved = lookup(symbol)

        # if user sends invalid symb, then anyways we get None
        if data_recieved == None:
            # apology for incorrect symbol
            return apology("Invalid symbol")
        # else, we got correct data
        # now we want to print it in quoted.html and we change the case to upper
        if symbol.upper() == data_recieved["symbol"]:
            round_price = round(data_recieved["price"], 2)
            return render_template("quoted.html", data=data_recieved)

        else:
            return apology("Invalid symbol")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
      # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        username = request.form.get("username")
        # while True:
        password = request.form.get("password")

            # if len(password) < 8:
            #     return apology("Make sure your password has atleast 8 letters")
            # elif not password.isdigit():
            #     return apology("Make sure your password has a number in it")
            # elif not password.isupper(): 
            #     return apology("Make sure your password has a capital letter in it")
            # else:
            #     return apology("Your password seems fine")
            #     break

        #if username is not provided
        if not username:
            return apology("must provide username", 400)
        #if username already present in the database
        used_usernames = []
        usernames = db.execute("select username from users")
        
        for entry in usernames:
            used_usernames.append(entry["username"])
        
        if username in used_usernames:
            return apology("this username already exist", 400)
        #if user forget to input password
        if not password:
            return apology("must provide password", 400)
        #if user forget to confirm password
        if not request.form.get("confirmation"):
            return apology("you must confirm the password")

        #checking if the entered password and the confirmed password are same
        if password == request.form.get("confirmation"):
        #hashing the user's password
            hash_password = generate_password_hash(password)

        #inserting the username, hashed password in the database
            rows = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash_password)
        else:
            return apology("Password doesn't match, type again")
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute("SELECT distinct(stock) from purchase where user_id = ?", session["user_id"])

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        shares = int(shares)

        print("Recieved symbol : ", symbol)
        print("Recieved shares : ", shares)

        no_of_shares = db.execute("SELECT sum(stock_count) from purchase where user_id = ? and stock = ?", session["user_id"], symbol)
        no_of_shares = no_of_shares[0]['sum(stock_count)']
        print(no_of_shares)

        data_recieved = lookup(symbol)
        # store the price information of the required stock
        latest_price = data_recieved["price"]
        latest_price = float(latest_price)

        if not symbol:
            return apology("must provide symbol", 403)
        if shares > no_of_shares:
            return apology("The user does not own that many shares of the stock")
        
        updating = db.execute("UPDATE users set cash = cash + ? where id = ?", shares * latest_price, session["user_id"])
        shareupdate = db.execute("UPDATE purchase set stock_count = stock_count - ? where user_id = ?", shares, session["user_id"])
        currentDateTime = datetime.datetime.now()

        insert_history = db.execute("insert into history(id, Symbol, Shares, Price, Transacted) VALUES (?, ?, ?, ?, ?)", 
                                    session["user_id"], symbol, shares, latest_price, currentDateTime)
        return redirect("/")
    return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)