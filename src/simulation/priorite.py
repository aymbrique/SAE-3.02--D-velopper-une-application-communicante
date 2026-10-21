"""Rangement des voitures et espace occupe par les vehicules."""

from math import cos, hypot, radians, sin

PULL_OVER = 26.0
SIDE_SPEED = 30.0
LOOK_AHEAD = 220.0
PASS_MARGIN = 65.0


def corners(vehicle, position, padding=0.0):
    x, y, angle = position
    length, width = (28, 15) if vehicle.kind == "car" else (36, 18)
    front = (cos(radians(angle)), sin(radians(angle)))
    right = (-front[1], front[0])
    return tuple((x + a * (length / 2 + padding) * front[0]
                  + b * (width / 2 + padding) * right[0],
                  y + a * (length / 2 + padding) * front[1]
                  + b * (width / 2 + padding) * right[1])
                 for a, b in ((-1, -1), (-1, 1), (1, 1), (1, -1)))


def bodies_clear(first, position, second, other_position):
    """Rectangles orientes, avec 3 unites libres entre les carrosseries."""
    a = corners(first, position, 1.5)
    b = corners(second, other_position, 1.5)
    for angle in (position[2], position[2] + 90,
                  other_position[2], other_position[2] + 90):
        dx, dy = cos(radians(angle)), sin(radians(angle))
        first_axis = [x * dx + y * dy for x, y in a]
        second_axis = [x * dx + y * dy for x, y in b]
        if max(first_axis) <= min(second_axis) or max(second_axis) <= min(first_axis):
            return True
    return False


def beside_rescue(car, rescue):
    """Meme route ou voie opposee, devant un secours proche ou juste depasse."""
    if not rescue.busy or rescue.dwell_remaining > 0:
        return False
    x, y, angle = car.route.sample(car.distance)
    start = max(0.0, rescue.distance - PASS_MARGIN)
    end = min(rescue.route.length, rescue.distance + LOOK_AHEAD)
    distance = start
    while distance <= end:
        rx, ry, heading = rescue.route.sample(distance)
        if (abs(cos(radians(angle - heading))) > .96
                and hypot(x - rx, y - ry) < 76):
            return True
        distance += 10
    return False
