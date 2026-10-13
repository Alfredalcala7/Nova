"""Plain-language terms: a starter list plus the student's own terms, all stored on this computer."""
import sqlite3
from contextlib import closing

from database.db_manager import get_connection
from services.study_service import ValidationError, _fetch_all, _write

MAX_TERM_LENGTH = 60
MAX_EXPLANATION_LENGTH = 1500
MAX_EXAMPLE_LENGTH = 500

# (term, plain-language explanation, example). Written for Nova; students should check them against their textbook.
STARTER_TERMS = [
    ("Variable", "A name that holds a value so you can use it later. Think of a labeled box: the label is the name, and what is inside can change.", "age = 18"),
    ("Function", "A named set of steps you can run whenever you need it. You write the steps once and reuse them, like a recipe.", "def greet(name):\n    print('Hello', name)"),
    ("Parameter", "A placeholder name in a function's definition for a value it will receive. The actual value you pass in when you call the function is called an argument.", "def greet(name):   # name is the parameter\ngreet('Ana')        # 'Ana' is the argument"),
    ("Class", "A blueprint that describes what something has (its data) and what it can do (its methods). A class by itself is only the plan, not the thing.", "class Dog:\n    def bark(self):\n        print('Woof')"),
    ("Object", "One real thing made from a class. If the class is the blueprint of a house, an object is an actual house built from it.", "my_dog = Dog()"),
    ("Instantiate", "To create an object from a class. You instantiate a class the way a builder builds a house from a blueprint, and each house is its own separate thing.", "my_dog = Dog()   # instantiates Dog; my_dog is the new object"),
    ("Attribute", "A piece of data that belongs to an object, such as a dog's name. It works like a variable stored inside the object.", "my_dog.name = 'Bantay'"),
    ("Method", "A function that belongs to a class, so it is something an object can do. You call it on an object with a dot.", "my_dog.bark()"),
    ("Inheritance", "When a new class reuses and extends an existing class, like a child who gets traits from a parent and can add its own. It saves you from rewriting the same code.", "class Puppy(Dog):   # Puppy inherits everything from Dog\n    def play(self):\n        print('Playing')"),
    ("Loop", "A way to repeat steps without writing them again and again. A for loop repeats once for each item in a collection, and a while loop repeats as long as a condition stays true.", "for number in range(3):\n    print(number)"),
    ("List", "An ordered collection of items kept under one name. You can add, remove and look up items by their position, which starts at 0.", "fruits = ['mango', 'banana']\nprint(fruits[0])   # mango"),
    ("Exception", "An error that happens while a program is running, such as dividing by zero. You can catch it with try and except so the program does not crash.", "try:\n    10 / 0\nexcept ZeroDivisionError:\n    print('Cannot divide by zero')"),
]


def _clean(term, explanation, example):
    term = " ".join(term.split())
    explanation, example = explanation.strip(), example.strip()
    if not term:
        raise ValidationError("The term cannot be empty.")
    if len(term) > MAX_TERM_LENGTH:
        raise ValidationError(f"The term must be {MAX_TERM_LENGTH} characters or fewer.")
    if not explanation:
        raise ValidationError("The explanation cannot be empty.")
    if len(explanation) > MAX_EXPLANATION_LENGTH:
        raise ValidationError(f"The explanation must be {MAX_EXPLANATION_LENGTH} characters or fewer.")
    if len(example) > MAX_EXAMPLE_LENGTH:
        raise ValidationError(f"The example must be {MAX_EXAMPLE_LENGTH} characters or fewer.")
    return term, explanation, example


def list_terms(query=""):
    query = query.strip()
    sql = "SELECT id, term, explanation, example, is_starter FROM glossary_terms"
    if not query:
        return _fetch_all(sql + " ORDER BY term")
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")  # search the text literally
    return _fetch_all(sql + " WHERE term LIKE ? ESCAPE '\\' ORDER BY term", (f"%{escaped}%",))


def add_term(term, explanation, example=""):
    term, explanation, example = _clean(term, explanation, example)
    try:
        return _write("INSERT INTO glossary_terms (term, explanation, example) VALUES (?, ?, ?)",
                      (term, explanation, example))
    except sqlite3.IntegrityError:
        raise ValidationError(f'A term named "{term}" already exists.') from None


def update_term(term_id, term, explanation, example=""):
    term, explanation, example = _clean(term, explanation, example)
    try:
        _write("UPDATE glossary_terms SET term = ?, explanation = ?, example = ?, is_starter = 0 WHERE id = ?",
               (term, explanation, example, term_id))
    except sqlite3.IntegrityError:
        raise ValidationError(f'A term named "{term}" already exists.') from None


def delete_term(term_id):
    _write("DELETE FROM glossary_terms WHERE id = ?", (term_id,))


def load_starter_terms():
    """Add any starter terms that are missing. Returns how many were added (0 if all are already there)."""
    with closing(get_connection()) as connection, connection:
        cursor = connection.executemany(
            "INSERT OR IGNORE INTO glossary_terms (term, explanation, example, is_starter) VALUES (?, ?, ?, 1)",
            STARTER_TERMS)
        return cursor.rowcount