import base64
import io
import json
import zlib
from typing import Optional
from PIL import Image

from pyvory.orm import DBConnect
from pyvory.orm.users import get_user_by_email
from pyvory.orm.utils import image_to_webp
from pyvory.recipes.recipe import Recipe

_get_recipe_base = """
SELECT r.id, r.author, r.title, r.description, r.steps, r.cooking_time, r.servings, GROUP_CONCAT(i.name, '~'), GROUP_CONCAT(i.quantity, '~'), GROUP_CONCAT(i.units, '~')
FROM recipes r 
JOIN ingredients i ON i.recipe_id = r.id
"""


def get_recipe_by_id(idx: int) -> Recipe:
    """Returns a recipe by its id from the db"""
    with DBConnect() as c:
        c.execute(_get_recipe_base + "WHERE r.id=?", (idx,))
        tup = c.fetchone()
    if not tup:
        raise FileNotFoundError(f"No recipe with id {idx}")
    return Recipe.from_tup(tup)


def get_recipe_picture(idx: int) -> bytes:
    """Returns the picture associated with the recipe"""
    with DBConnect() as c:
        c.execute("SELECT image FROM recipes WHERE id=?", (idx,))
        tup = c.fetchone()
        if not tup or not tup[0]:
            raise FileNotFoundError()
        return zlib.decompress(tup[0])


def update_recipe(email: str, recipe: Recipe, image: Optional[str] = None) -> Recipe:
    """Updates a recipe with corresponding id and reruns the new one if the user is the owner of the recipe"""
    user = get_user_by_email(email)
    if recipe.idx not in user.posts:
        raise Exception("Cannot edit recipe because the user doesn't own it")
    with DBConnect() as c:
        if image is not None:
            if image:
                image = zlib.compress(image_to_webp(base64.b64decode(image), 640))
            else:
                image = None
        else:
            image = c.execute("SELECT image FROM recipes WHERE id=?", (recipe.idx,)).fetchone()[0]
        c.execute(
            "UPDATE recipes SET author=?, title=?,description=?,steps=?,cooking_time=?,servings=?,image=? WHERE id=?",
            (recipe.author, recipe.title, recipe.description, json.dumps(recipe.steps), recipe.cooking_time,
             recipe.servings, image, recipe.idx))
        c.execute("DELETE FROM ingredients WHERE recipe_id=?", (recipe.idx,))
        c.executemany("INSERT INTO ingredients(name, quantity, units, recipe_id) VALUES(?, ?, ?, ?)",
                      [(r.name, r.quantity, r.units, recipe.idx) for r in recipe.ingredients])
    return recipe


def insert_recipe(r: Recipe, image: Optional[str] = None) -> Recipe:
    """Inserts a recipe and returns it with correct id"""
    if image:
        image = zlib.compress(image_to_webp(base64.b64decode(image), 640))
    else:
        image = None
    with DBConnect() as c:
        c.execute(
            "INSERT INTO recipes(author, title, description, steps, cooking_time, servings, image) VALUES(?,?,?,?,?,?,?)",
            (r.author, r.title, r.description, json.dumps(r.steps), r.cooking_time, r.servings, image))
        r.idx = c.execute("SELECT id FROM recipes WHERE rowid=?", (c.lastrowid,)).fetchone()[0]
        c.executemany("INSERT INTO ingredients(name, quantity, units, recipe_id) VALUES(?, ?, ?, ?)",
                      [(i.name, i.quantity, i.units, r.idx) for i in r.ingredients])
    return r
