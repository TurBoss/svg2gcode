#
# gcoder.py - python library for writing g-code
#
# Copyright (C) 2018 Sebastian Kuzminsky
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# 


from __future__ import print_function

import cairosvg.parser
import math
import os
import re
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'svgpathtools'))
import svgpathtools


class line(object):

    """The Line class represents a linear feed move (g1) to the specified
    endpoint.

    It can be used as an element in the list of moves passed to
    z_path2()."""

    def __init__(self, x=None, y=None, z=None):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self):
        have_arg = False
        r = "Line("

        if self.x is not None:
            r += "x=%.4f" % self.x
            have_arg = True

        if self.y is not None:
            if have_arg:
                r += ", "
            r += "y=%.4f" % self.y
            have_arg = True

        if self.z is not None:
            if have_arg:
                r += ", "
            r += "z=%.4f" % self.z
            have_arg = True

        r += ")"
        return r


class arc(object):

    """arc() is a base class representing a circular feed move (g2 or g3)
    to the specified endpoint.  It is not suitable for use by itself, you
    should use one of its subclasses, arc_cw() or arc_ccw(), instead."""

    def __init__(self, x=None, y=None, z=None, i=None, j=None, p=None):
        self.x = x
        self.y = y
        self.z = z
        self.i = i
        self.j = j
        self.p = p

    def __str__(self):
        have_arg = False
        r = self.__class__.__name__ + "("

        if self.x is not None:
            r += "x=%.4f" % self.x
            have_arg = True

        if self.y is not None:
            if have_arg:
                r += ", "
            r += "y=%.4f" % self.y
            have_arg = True

        if self.z is not None:
            if have_arg:
                r += ", "
            r += "z=%.4f" % self.z
            have_arg = True

        if self.i is not None:
            if have_arg:
                r += ", "
            r += "i=%.4f" % self.i
            have_arg = True

        if self.j is not None:
            if have_arg:
                r += ", "
            r += "j=%.4f" % self.j
            have_arg = True

        if self.p is not None:
            if have_arg:
                r += ", "
            r += "p=%.4f" % self.p
            have_arg = True

        r += ")"
        return r


class arc_cw(arc):
    """The arc_cw() class represents a circular clockwise feed move (g2)
    to the specified endpoint.

    It can be used as an element in the list of moves passed to
    z_path2()."""

class arc_ccw(arc):
    """The arc_ccw() class represents a circular counter-clockwise feed
    move (g3) to the specified endpoint.

    It can be used as an element in the list of moves passed to
    z_path2()."""


class svg():
    def __init__(self, svg_file):
        self.svg_file = svg_file
        self.height = 0.0

        # svg coordinate * scale == mm
        self.scale = 1.0

        self.cairo = cairosvg.parser.Tree(url=self.svg_file)

        m = re.match('([0-9.]+)([a-zA-Z]*)', self.cairo['height'])
        if m == None:
            raise SystemExit, "failed to parse SVG height: %s" % c['height']

        self.height = float(m.group(1))

        if len(m.groups()) == 2:
            if m.group(2) == "mm":
                self.height = float(m.group(1))
            elif m.group(2) == '':
                # no units on the height implies 96 dpi
                # 1 inch/96 units * 25.4 mm/1 inch = 25.4/96 mm/unit
                self.scale = 25.4/96
            else:
                raise SystemExit, "unhandled SVG units '%s'" % m.group(2)
        else:
            raise SystemExit, "weird result from re"

        self.paths, self.attributes = svgpathtools.svg2paths(self.svg_file)


    def to_mm_x(self, x_mm):
        if type(x_mm) != float:
            raise SystemExit, 'non-float input'
        return x_mm * self.scale


    def to_mm_y(self, y_mm):
        if type(y_mm) != float:
            raise SystemExit, 'non-float input'
        return self.height - y_mm * self.scale


    def to_mm(self, xy):
        if type(xy) != complex:
            raise SystemExit, 'non-complex input'
        x = self.to_mm_x(xy.real)
        y = self.to_mm_y(xy.imag)
        return (x, y)


def split_path_at_intersections(path_list, debug=False):

    """`path_list` is a list of connected path segments.  This function
    identifies each place where the path intersects intself, and splits
    each non-self-intersecting subset of the path into a separate
    path list.  This may involve splitting segments.

    Returns a list of path lists."""


    def find_earliest_intersection(path_list, this_seg_index):
        this_seg = path_list[this_seg_index]
        if debug: print("looking for earliest intersection of this seg(%d):" % this_seg_index, this_seg, file=sys.stderr)

        earliest_this_t = None
        earliest_other_seg_index = None
        earliest_other_t = None

        for other_seg_index in range(this_seg_index+2, len(path_list)):
            other_seg = path_list[other_seg_index]
            if debug: print("    other[%d]:" % other_seg_index, other_seg, file=sys.stderr)
            intersections = this_seg.intersect(other_seg)
            if len(intersections) == 0:
                continue;
            if debug: print("        intersect!", file=sys.stderr)

            # The intersection that comes earliest in `this_seg` is
            # the interesting one, except that intersections at the
            # segments' endpoints don't count.
            for intersection in intersections:
                if complex_close_enough(intersection[0], 0.0) or complex_close_enough(intersection[0], 1.0):
                    continue

                if (earliest_this_t == None) or (intersection[0] < earliest_this_t):
                    if debug: print("        earliest!", file=sys.stderr)
                    earliest_this_t = intersection[0]
                    earliest_other_seg_index = other_seg_index
                    earliest_other_t = intersection[1]

        return earliest_this_t, earliest_other_seg_index, earliest_other_t


    if debug: print("splitting path:", file=sys.stderr)
    if debug: print("    ", path_list, file=sys.stderr)

    # This is a list of pairs.  Each pair represents a place where the
    # input path crosses itself.  The two members of the pair are the
    # indexes of the segments that end at the intersection point.
    intersections = []

    this_seg_index = 0
    while this_seg_index < len(path_list):
        this_seg = path_list[this_seg_index]

        this_t, other_seg_index, other_t = find_earliest_intersection(path_list, this_seg_index)
        if this_t == None:
            this_seg_index += 1
            continue

        # Found the next intersection.  Split the segments and note
        # the intersection.

        other_seg = path_list[other_seg_index]

        this_first_seg, this_second_seg = this_seg.split(this_t)
        other_first_seg, other_second_seg = other_seg.split(other_t)
        if debug: print("split this seg:", this_seg, file=sys.stderr)
        if debug: print("    t:", this_t, file=sys.stderr)
        if debug: print("    ", this_first_seg, file=sys.stderr)
        if debug: print("    ", this_second_seg, file=sys.stderr)
        if debug: print("split other seg:", other_seg, file=sys.stderr)
        if debug: print("    t:", other_t, file=sys.stderr)
        if debug: print("    ", other_first_seg, file=sys.stderr)
        if debug: print("    ", other_second_seg, file=sys.stderr)

        # FIXME: This fixup is bogus, but the two segments'
        # `t` parameters don't put the intersection at the
        # same point...
        other_first_seg.end = this_first_seg.end
        other_second_seg.start = other_first_seg.end

        assert(complex_close_enough(this_first_seg.end, this_second_seg.start))
        assert(complex_close_enough(this_first_seg.end, other_first_seg.end))
        assert(complex_close_enough(this_first_seg.end, other_second_seg.start))

        assert(complex_close_enough(this_first_seg.start, this_seg.start))
        assert(complex_close_enough(this_second_seg.end, this_seg.end))

        assert(complex_close_enough(other_first_seg.start, other_seg.start))
        assert(complex_close_enough(other_second_seg.end, other_seg.end))

        # Replace the old (pre-split) this_seg with the first sub-segment.
        path_list[this_seg_index] = this_first_seg

        # Insert the second sub-segment after the first one.
        path_list.insert(this_seg_index+1, this_second_seg)

        # We inserted a segment before other_seg, so we increment
        # its index.
        other_seg_index += 1

        # Replace the old (pre-split) other_seg with the first sub-segment.
        path_list[other_seg_index] = other_first_seg

        # Insert the second sub-segment after the first one.
        path_list.insert(other_seg_index+1, other_second_seg)

        for i in range(len(intersections)):
            if debug: print("bumping intersection:", file=sys.stderr)
            if debug: print("    ", intersections[i], file=sys.stderr)
            if intersections[i][1] >= this_seg_index:
                intersections[i][1] += 1  # for this_seg that got split
            if intersections[i][1] >= other_seg_index:
                intersections[i][1] += 1  # for other_seg that got split
            if debug: print("    ", intersections[i], file=sys.stderr)

        # Add this new intersection we just made.
        i = [this_seg_index, other_seg_index]
        if debug: print("    new:", i, file=sys.stderr)
        intersections.append(i)

        # Look for intersections in the remainder of this_seg (the second
        # part of the split).
        this_seg_index += 1

    if debug: print("found some intersections:", file=sys.stderr)
    for i in intersections:
        if debug: print("    ", i, file=sys.stderr)
        if debug: print("        ", path_list[i[0]], file=sys.stderr)
        if debug: print("        ", path_list[i[1]], file=sys.stderr)

    paths = []
    while True:
        if debug: print("starting a new path", file=sys.stderr)
        path = []
        # Start at the first unused segment
        seg_index = 0
        for seg_index in range(len(path_list)):
            if path_list[seg_index] != None:
                break

        while seg_index < len(path_list):
            if path_list[seg_index] == None:
                # Done with this path.
                break

            if debug: print("    adding segment %d:" % seg_index, path_list[seg_index], file=sys.stderr)
            path.append(path_list[seg_index])
            path_list[seg_index] = None

            i = None
            for i in intersections:
                if seg_index == i[0] or seg_index == i[1]:
                    break
            if debug: print("i:", i, file=sys.stderr)
            if debug: print("seg_index:", seg_index, file=sys.stderr)
            if (i is not None) and (i[0] == seg_index):
                # This segment is the first entrance to an intersection,
                # take the second exit.
                if debug: print("    intersection!", file=sys.stderr)
                seg_index = i[1] + 1
            elif (i is not None) and (i[1] == seg_index):
                # This segment is the second entrance to an intersection,
                # take the first exit.
                if debug: print("    intersection!", file=sys.stderr)
                seg_index = i[0] + 1
            else:
                # This segment doesn't end in an intersection, just go
                # to the next one.
                seg_index += 1

        if path == []:
            break

        paths.append(path)

    return paths


def approximate_path_area(path):

    """Approximates the path area by converting each Arc to 1,000
    Lines."""

    assert(path.isclosed())
    tmp = svgpathtools.path.Path()
    for seg in path:
        if type(seg) == svgpathtools.path.Arc:
            for i in range(0, 1000):
                t0 = i/1000.0
                t1 = (i+1)/1000.0
                l = svgpathtools.path.Line(start=seg.point(t0), end=seg.point(t1))
                tmp.append(l)
        else:
            tmp.append(seg)
    return tmp.area()


def offset_paths(path, offset_distance, steps=100, debug=False):
    """Takes an svgpathtools.path.Path object, `path`, and a float
    distance, `offset_distance`, and returns the parallel offset curves
    (in the form of a list of svgpathtools.path.Path objects)."""


    def is_enclosed(path, check_paths):

        """`path` is an svgpathtools.path.Path object, `check_paths`
        is a list of svgpath.path.Path objects.  This function returns
        True if `path` lies inside any of the paths in `check_paths`,
        and returns False if it lies outside all of them."""

        seg = path[0]
        point = seg.point(0.5)

        for i in range(len(check_paths)):
            test_path = check_paths[i]
            if path == test_path:
                continue
            # find outside_point, which lies outside other_path
            (xmin, xmax, ymin, ymax) = test_path.bbox()
            outside_point = complex(xmax+100, ymax+100)
            if svgpathtools.path_encloses_pt(point, outside_point, test_path):
                if debug: print("point is within path", i, file=sys.stderr)
                return True
        return False


    # This only works on closed paths.
    if debug: print("input path:", file=sys.stderr)
    if debug: print(path, file=sys.stderr)
    if debug: print("offset:", offset_distance, file=sys.stderr)
    assert(path.isclosed())


    #
    # First generate a list of Path elements (Lines and Arcs),
    # corresponding to the offset versions of the Path elements in the
    # input path.
    #

    if debug: print("generating offset segments...", file=sys.stderr)

    offset_path_list = []
    for seg in path:
        if type(seg) == svgpathtools.path.Line:
            start = seg.point(0) + (offset_distance * seg.normal(0))
            end = seg.point(1) + (offset_distance * seg.normal(1))
            offset_path_list.append(svgpathtools.Line(start, end))
            if debug: print("    ", offset_path_list[-1], file=sys.stderr)

        elif type(seg) == svgpathtools.path.Arc and (seg.radius.real == seg.radius.imag):
            # Circular arcs remain arcs, elliptical arcs become linear
            # approximations below.
            #
            # Polygons (input paths) are counter-clockwise.
            #
            # Positive offsets are to the inside of the polygon, negative
            # offsets are to the outside.
            #
            # If this arc is counter-clockwise (sweep == False),
            # *subtract* the `offset_distance` from its radius, so
            # insetting makes the arc smaller and outsetting makes
            # it larger.
            #
            # If this arc is clockwise (sweep == True), *add* the
            # `offset_distance` from its radius, so insetting makes the
            # arc larger and outsetting makes it smaller.
            #
            # If the radius of the offset arc is negative, use its
            # absolute value and invert the sweep.

            if seg.sweep == False:
                new_radius = seg.radius.real - offset_distance
            else:
                new_radius = seg.radius.real + offset_distance

            start = seg.point(0) + (offset_distance * seg.normal(0))
            end = seg.point(1) + (offset_distance * seg.normal(1))
            sweep = seg.sweep

            flipped = False
            if new_radius < 0.0:
                if debug: print("    inverting Arc!", file=sys.stderr)
                flipped = True
                new_radius = abs(new_radius)
                sweep = not sweep

            if new_radius > 0.002:
                radius = complex(new_radius, new_radius)
                offset_arc = svgpathtools.path.Arc(
                    start = start,
                    end = end,
                    radius = radius,
                    rotation = seg.rotation,
                    large_arc = seg.large_arc,
                    sweep = sweep
                )
                offset_path_list.append(offset_arc)
            elif new_radius > epsilon:
                # Offset Arc radius is smaller than the minimum that
                # LinuxCNC accepts, replace with a Line.
                if debug: print("    arc too small, replacing with a line", file=sys.stderr)
                if flipped:
                    old_start = start
                    start = end
                    end = old_start
                offset_arc = svgpathtools.path.Line(start = start, end = end)
                offset_path_list.append(offset_arc)
            else:
                # Zero-radius Arc, it disappeared.
                if debug: print("    arc way too small, removing", file=sys.stderr)
                continue
            if debug: print("    ", offset_path_list[-1], file=sys.stderr)

        else:
            # Deal with any segment that's not a line or a circular arc.
            # This includes elliptic arcs and bezier curves.  Use linear
            # approximation.
            #
            # FIXME: Steps should probably be computed dynamically to make
            #     the length of the *offset* line segments manageable.
            points = []
            for k in range(steps+1):
                t = k / float(steps)
                normal = seg.normal(t)
                offset_vector = offset_distance * normal
                points.append(seg.point(t) + offset_vector)
            for k in range(len(points)-1):
                start = points[k]
                end = points[k+1]
                offset_path_list.append(svgpathtools.Line(start, end))
            if debug: print("    (long list of short lines)", file=sys.stderr)


    #
    # Find all the places where one segment intersects the next, and
    # trim to the intersection.
    #

    if debug: print("trimming intersecting segments...", file=sys.stderr)

    for i in range(len(offset_path_list)):
        this_seg = offset_path_list[i]
        if (i+1) < len(offset_path_list):
            next_seg = offset_path_list[i+1]
        else:
            next_seg = offset_path_list[0]

        # FIXME: I'm not sure about this part.
        if debug: print("intersecting", file=sys.stderr)
        if debug: print("    this", this_seg, file=sys.stderr)
        if debug: print("    next", next_seg, file=sys.stderr)
        intersections = this_seg.intersect(next_seg)
        if debug: print("    intersections:", intersections, file=sys.stderr)
        if len(intersections) > 0:
            intersection = intersections[0]
            point = this_seg.point(intersection[0])
            if debug: print("    intersection point:", point, file=sys.stderr)
            if not complex_close_enough(point, this_seg.end):
                this_seg.end = this_seg.point(intersection[0])
                next_seg.start = this_seg.end


    #
    # Find all the places where adjacent segments do not end/start close
    # to each other, and join them with Arcs.
    #

    if debug: print("joining non-connecting segments with arcs...", file=sys.stderr)

    joined_offset_path_list = []
    for i in range(len(offset_path_list)):
        this_seg = offset_path_list[i]
        if (i+1) < len(offset_path_list):
            next_seg = offset_path_list[i+1]
        else:
            next_seg = offset_path_list[0]

        if complex_close_enough(this_seg.end, next_seg.start):
            joined_offset_path_list.append(this_seg)
            continue

        if debug: print("these segments don't touch end to end:", file=sys.stderr)
        if debug: print(this_seg, file=sys.stderr)
        if debug: print(next_seg, file=sys.stderr)
        if debug: print("    error:", this_seg.end-next_seg.start, file=sys.stderr)

        # FIXME: Choose values for `large_arc` and `sweep` correctly here.
        # I think the goal is to make the joining arc tangent to the segments it joins.
        # large_arc should always be False
        # sweep means "clockwise" (but +Y is down)
        if debug: print("determining joining arc:", file=sys.stderr)
        if debug: print("    this_seg ending normal:", this_seg.normal(1), file=sys.stderr)
        if debug: print("    next_seg starting normal:", next_seg.normal(0), file=sys.stderr)

        sweep_arc = svgpathtools.path.Arc(
            start = this_seg.end,
            end = next_seg.start,
            radius = complex(offset_distance, offset_distance),
            rotation = 0,
            large_arc = False,
            sweep = True
        )
        sweep_start_error = this_seg.normal(1) - sweep_arc.normal(0)
        sweep_end_error = next_seg.normal(0) - sweep_arc.normal(1)
        sweep_error = pow(abs(sweep_start_error), 2) + pow(abs(sweep_end_error), 2)
        if debug: print("    sweep arc starting normal:", sweep_arc.normal(0), file=sys.stderr)
        if debug: print("    sweep arc ending normal:", sweep_arc.normal(1), file=sys.stderr)
        if debug: print("    sweep starting error:", sweep_start_error, file=sys.stderr)
        if debug: print("    sweep end error:", sweep_end_error, file=sys.stderr)
        if debug: print("    sweep error:", sweep_error, file=sys.stderr)

        antisweep_arc = svgpathtools.path.Arc(
            start = this_seg.end,
            end = next_seg.start,
            radius = complex(offset_distance, offset_distance),
            rotation = 0,
            large_arc = False,
            sweep = False
        )
        antisweep_start_error = this_seg.normal(1) - antisweep_arc.normal(0)
        antisweep_end_error = next_seg.normal(0) - antisweep_arc.normal(1)
        antisweep_error = pow(abs(antisweep_start_error), 2) + pow(abs(antisweep_end_error), 2)
        if debug: print("    antisweep arc starting normal:", antisweep_arc.normal(0), file=sys.stderr)
        if debug: print("    antisweep arc ending normal:", antisweep_arc.normal(1), file=sys.stderr)
        if debug: print("    antisweep starting error:", antisweep_start_error, file=sys.stderr)
        if debug: print("    antisweep end error:", antisweep_end_error, file=sys.stderr)
        if debug: print("    antisweep error:", antisweep_error, file=sys.stderr)

        joining_arc = None
        if sweep_error < antisweep_error:
            if debug: print("joining arc is sweep", file=sys.stderr)
            joining_arc = sweep_arc
        else:
            if debug: print("joining arc is antisweep", file=sys.stderr)
            joining_arc = antisweep_arc

        if debug: print("joining arc:", file=sys.stderr)
        if debug: print(joining_arc, file=sys.stderr)
        if debug: print("    length:", joining_arc.length(), file=sys.stderr)
        if debug: print("    start-end distance:", joining_arc.start-joining_arc.end, file=sys.stderr)

        # FIXME: this is kind of arbitrary
        joining_seg = joining_arc
        if joining_arc.length() < 1e-4:
            joining_seg = svgpathtools.path.Line(joining_arc.start, joining_arc.end)
            if debug: print("    too short!  replacing with a line:", joining_seg, file=sys.stderr)

        joined_offset_path_list.append(this_seg)
        joined_offset_path_list.append(joining_seg)

    offset_path_list = joined_offset_path_list


    #
    # Find the places where the path intersects itself, split into
    # multiple separate paths in those places.
    #

    if debug: print("splitting path at intersections...", file=sys.stderr)

    offset_paths_list = split_path_at_intersections(offset_path_list)


    #
    # Smooth the path: adjacent segments whose start/end points are
    # "close enough" to each other are adjusted so they actually touch.
    #
    # FIXME: is this still needed?
    #

    if debug: print("smoothing paths...", file=sys.stderr)

    for path_list in offset_paths_list:
        for i in range(len(path_list)):
            this_seg = path_list[i]
            if (i+1) < len(path_list):
                next_seg = path_list[i+1]
            else:
                next_seg = path_list[0]
            if complex_close_enough(this_seg.end, next_seg.start):
                next_seg.start = this_seg.end
            else:
                if debug: print("gap in the path (seg %d and following):" % i, file=sys.stderr)
                if debug: print("    this_seg.end:", this_seg.end, file=sys.stderr)
                if debug: print("    next_seg.start:", next_seg.start, file=sys.stderr)


    #
    # Convert each path list to a Path object and sanity check.
    #

    if debug: print("converting path lists to paths...", file=sys.stderr)

    offset_paths = []
    for path_list in offset_paths_list:
        offset_path = svgpathtools.Path(*path_list)
        if debug: print("offset path:", file=sys.stderr)
        if debug: print(offset_path, file=sys.stderr)
        assert(offset_path.isclosed())
        offset_paths.append(offset_path)


    #
    # The set of paths we got from split_path_at_intersections() has
    # zero or more 'true paths' that we actually want to return, plus
    # zero or more 'false paths' that should be discarded.
    #
    # When offsetting a path to the inside, the false paths will be
    # outside the true path and will wind in the opposite direction of
    # the input path.
    #
    # When offsetting a path to the outside, the false paths will be
    # inside the true paths, and will wind in the same direction as the
    # input path.
    #
    # [citation needed]
    #

    if debug: print("pruning false paths...", file=sys.stderr)

    path_area = approximate_path_area(path)
    if debug: print("input path area:", path_area, file=sys.stderr)

    keepers = []

    if offset_distance > 0:
        # The offset is positive (inwards), discard paths with opposite
        # direction from input path.
        for offset_path in offset_paths:
            if debug: print("checking path:", offset_path, file=sys.stderr)
            offset_path_area = approximate_path_area(offset_path)
            if debug: print("offset path area:", offset_path_area, file=sys.stderr)
            if path_area * offset_path_area < 0.0:
                # Input path and offset path go in the opposite directions,
                # drop offset path.
                if debug: print("wrong direction, dropping", file=sys.stderr)
                continue
            keepers.append(offset_path)

    else:
        # The offset is negative (outwards), discard paths that lie
        # inside any other path and have the same winding direction as
        # the input path.
        for offset_path in offset_paths:
            if debug: print("checking path:", offset_path, file=sys.stderr)
            if is_enclosed(offset_path, offset_paths):
                if debug: print("    enclosed", file=sys.stderr)
                # This path is enclosed, check the winding direction.
                offset_path_area = approximate_path_area(offset_path)
                if debug: print("offset path area:", offset_path_area, file=sys.stderr)
                if path_area * offset_path_area > 0.0:
                    if debug: print("    winding is the same as input, dropping", file=sys.stderr)
                    continue
                else:
                    if debug: print("    winding is opposite input", file=sys.stderr)
            else:
                if debug: print("    not enclosed", file=sys.stderr)
            if debug: print("    keeping", file=sys.stderr)
            keepers.append(offset_path)

    offset_paths = keepers

    return offset_paths


def path_to_gcode(svg, path, z_traverse=10, z_approach=None, z_top_of_material=0, z_cut_depth=0, lead_in=True, lead_out=True, feed=None, plunge_feed=None):
    absolute_arc_centers()
    (x, y) = svg.to_mm(path[0].start)

    if z_approach == None:
        z_approach = 0.5 + z_top_of_material

    if lead_in:
        g0(z=z_traverse)
        g0(x=x, y=y)

    spindle_on()

    if lead_in:
        g0(z=z_approach)
        if plunge_feed:
            set_feed_rate(plunge_feed)
        elif feed:
            set_feed_rate(feed)
        g1(z=z_cut_depth)
        if plunge_feed and feed:
            set_feed_rate(feed)
    else:
        if feed:
            set_feed_rate(feed)
        g1(x=x, y=y)

    for element in path:
        if type(element) == svgpathtools.path.Line:
            (start_x, start_y) = svg.to_mm(element.start)
            (end_x, end_y) = svg.to_mm(element.end)
            g1(x=end_x, y=end_y)
        elif type(element) == svgpathtools.path.Arc:
            # FIXME: g90.1 or g91.1?
            if element.radius.real != element.radius.imag:
                raise ValueError, "arc radii differ: %s", element
            (end_x, end_y) = svg.to_mm(element.end)
            (center_x, center_y) = svg.to_mm(element.center)
            if element.sweep:
                g2(x=end_x, y=end_y, i=center_x, j=center_y)
            else:
                g3(x=end_x, y=end_y, i=center_x, j=center_y)
        else:
            # Deal with any segment that's not a line or a circular arc,
            # this includes elliptic arcs and bezier curves.  Use linear
            # approximation.
            #
            # FIXME: The number of steps should probably be dynamically
            #     adjusted to make the length of the *offset* line
            #     segments manageable.
            steps = 1000
            for k in range(steps+1):
                t = k / float(steps)
                end = element.point(t)
                (end_x, end_y) = svg.to_mm(end)
                g1(x=end_x, y=end_y)

    if lead_out:
        g1(z=z_approach)
        g0(z=z_traverse)


# These keep track of where the most recent move left the controlled
# point, or None if the position is not known.
current_x = None
current_y = None
current_z = None
current_a = None
current_b = None
current_c = None
current_u = None
current_v = None
current_w = None


# When comparing floats, a difference of less than epsilon counts as no
# difference at all.
epsilon = 1e-6

def close_enough(a, b):
    """Returns True if the two numbers `a` and `b` are within `epsilon`
    (1e-6) of each other, False if they're farther apart."""
    return abs(a - b) < epsilon

def complex_close_enough(a, b):
    """Returns True if the two complex numbers `a` and `b` are within
    `epsilon` (1e-6) of each other, False if they're farther apart."""
    diff = complex(a.real - b.real, a.imag - b.imag)
    mag = math.sqrt(pow(diff.real, 2) + pow(diff.imag, 2))
    if mag < epsilon:
        return True
    return False


def init():
    print()
    print("; init")
    print("G20          (inch)")
    print("G17          (xy plane)")
    print("G90          (absolute)")
    print("G91.1        (arc centers are relative to arc starting point)")
    cutter_comp_off()
    print("G54          (switch to coordinate system 1)")
    print("G94          (units/minute feed mode)")
    print("G99          (in canned cycles, retract to the Z coordinate specified by the R word)")
    print("G64 P0.0005  (enable path blending, but stay within 0.0005 of the programmed path)")
    print("G49          (turn off tool length compensation)")
    print("G80          (turn off canned cycles)")
    print()


def comment(msg):
    if msg:
        print(";", msg)
    else:
        print()


def absolute():
    print("G90")


def absolute_arc_centers():
    print("G90.1")


def relative_arc_centers():
    print("G91.1")


def spindle_on():
    print("M3")


def spindle_off():
    print("M5")


def path_blend(tolerance=None):
    print("G64 P%.4f (enable path blending with tolerance)" % tolerance)


def quill_up():
    absolute()
    cutter_comp_off()
    print("G53 G0 Z0")
    current_z = None
    spindle_off()


def presentation_position():
    imperial()
    quill_up()

    # rapid to presentation position
    # table centered in X, all the way forward towards the user
    print("G53 G0 X9 Y12")
    current_x = None
    current_y = None


def m2():
    print()
    print("M2")


def done():
    print()
    print("; done")
    presentation_position()
    print("M2")


def imperial():
    print("G20")


def metric():
    print("G21")


def set_feed_rate(feed_rate_units_per_minute):
    print("F %.4f" % feed_rate_units_per_minute)


def speed(spindle_rpm):
    print("S %d" % spindle_rpm)


# FIXME: g0(path) should be merged or replaced by z_path() somehow
def g0(path=None, x=None, y=None, z=None, a=None, b=None, c=None, u=None, v=None, w=None):
    global current_x
    global current_y
    global current_z
    global current_a
    global current_b
    global current_c
    global current_u
    global current_v
    global current_w

    if path is not None:
        print()
        print("; g0 path")
        for waypoint in path:
            g0(**waypoint)
        print()
    else:
        print("G0", end='')
        if x is not None:
            current_x = x
            print(" X%.4f" % x, end='')
        if y is not None:
            current_y = y
            print(" Y%.4f" % y, end='')
        if z is not None:
            current_z = z
            print(" Z%.4f" % z, end='')
        if a is not None:
            current_a = a
            print(" A%.4f" % a, end='')
        if b is not None:
            current_b = b
            print(" B%.4f" % b, end='')
        if c is not None:
            current_c = c
            print(" C%.4f" % c, end='')
        if u is not None:
            current_u = u
            print(" U%.4f" % u, end='')
        if v is not None:
            current_v = v
            print(" V%.4f" % v, end='')
        if w is not None:
            current_w = w
            print(" W%.4f" % w, end='')
        print()


def g1(path=None, x=None, y=None, z=None, a=None, b=None, c=None, u=None, v=None, w=None):
    global current_x
    global current_y
    global current_z
    global current_a
    global current_b
    global current_c
    global current_u
    global current_v
    global current_w

    if path is not None:
        print()
        print("; g1 path")
        for waypoint in path:
            g1(**waypoint)
        print()
    else:
        print("G1", end='')
        if x is not None:
            current_x = x
            print(" X%.4f" % x, end='')
        if y is not None:
            current_y = y
            print(" Y%.4f" % y, end='')
        if z is not None:
            current_z = z
            print(" Z%.4f" % z, end='')
        if a is not None:
            current_a = a
            print(" A%.4f" % a, end='')
        if b is not None:
            current_b = b
            print(" B%.4f" % b, end='')
        if c is not None:
            current_c = c
            print(" C%.4f" % c, end='')
        if u is not None:
            current_u = u
            print(" U%.4f" % u, end='')
        if v is not None:
            current_v = v
            print(" V%.4f" % v, end='')
        if w is not None:
            current_w = w
            print(" W%.4f" % w, end='')
        print()


def g2(x=None, y=None, z=None, i=None, j=None, p=None):
    global current_x
    global current_y
    global current_z

    """Clockwise arc feed."""
    if i is None and j is None:
        raise TypeError, "gcoder.g2() without i or j"
    print("G2", end='')
    if x is not None:
        current_x = x
        print(" X%.4f" % x, end='')
    if y is not None:
        current_y = y
        print(" Y%.4f" % y, end='')
    if z is not None:
        current_z = z
        print(" Z%.4f" % z, end='')
    if i is not None: print(" I%.4f" % i, end='')
    if j is not None: print(" J%.4f" % j, end='')
    if p is not None: print(" P%.4f" % p, end='')
    print()


def g3(x=None, y=None, z=None, i=None, j=None, p=None):
    global current_x
    global current_y
    global current_z

    """Counter-clockwise arc feed."""
    if i is None and j is None:
        raise TypeError, "gcoder.g3() without i or j"
    print("G3", end='')
    if x is not None:
        current_x = x
        print(" X%.4f" % x, end='')
    if y is not None:
        current_y = y
        print(" Y%.4f" % y, end='')
    if z is not None:
        current_z = z
        print(" Z%.4f" % z, end='')
    if i is not None: print(" I%.4f" % i, end='')
    if j is not None: print(" J%.4f" % j, end='')
    if p is not None: print(" P%.4f" % p, end='')
    print()


#
# Cutter compensation handling.
#

def cutter_comp_off():
    print("G40          (cutter comp off)")

def cancel_cutter_comp():
    print("; gcoder: calling program used obsolete cancel_cutter_comp() function, use cutter_comp_off() instead")
    cutter_comp_off()

def g40():
    print("; gcoder: calling program used obsolete g40() function, use cutter_comp_off() instead")
    cutter_comp_off()


def cutter_comp_left(**kwargs):

    """Enable cutter diameter compensation on the left side of the
    programmed path.

    When called with no argument, uses the diameter of the currently
    loaded tool (from the tool table).

    When called with the `diameter` argument, uses the specified diameter.

    When called with the `tool` argument (and without the `diameter`
    argument), uses the diameter of the specified tool number (from the
    tool table)."""

    if 'diameter' in kwargs:
        print("G41.1 D%.4f   (cutter comp left, diameter mode)" % kwargs['diameter'])
    elif 'tool' in kwargs:
        print("G41 D%d   (cutter comp left, tool-number mode)" % kwargs['tool'])
    else:
        print("G41   (cutter comp left, current tool)")


def cutter_comp_right(**kwargs):

    """Enable cutter diameter compensation on the right side of the
    programmed path.

    When called with no argument, uses the diameter of the currently
    loaded tool (from the tool table).

    When called with the `diameter` argument, uses the specified diameter.

    When called with the `tool` argument (and without the `diameter`
    argument), uses the diameter of the specified tool number (from the
    tool table)."""

    if 'diameter' in kwargs:
        print("G42.1 D%.4f   (cutter comp right, diameter mode)" % kwargs['diameter'])
    elif 'tool' in kwargs:
        print("G42 D%d   (cutter comp right, tool-number mode)" % kwargs['tool'])
    else:
        print("G42   (cutter comp right, current tool)")

def g42_1(comp_diameter):
    print("; gcoder: calling program used obsolete g42_1() function, use cutter_comp_right() instead")
    cutter_comp_right(diameter=comp_diameter)


def g81(retract, x=None, y=None, z=None):
    global current_x
    global current_y
    global current_z

    print("G81", end='')
    if x is not None:
        current_x = x
        print(" X%.4f" % x, end='')
    if y is not None:
        current_y = y
        print(" Y%.4f" % y, end='')
    if z is not None:
        print(" Z%.4f" % z, end='')
    print(" R%.4f" % retract, end='')
    print()
    # FIXME: keep track of retract mode, set Z correctly here
    current_z = None


def g83(retract, delta, x=None, y=None, z=None):
    global current_x
    global current_y
    global current_z

    print("G83", end='')
    if x is not None:
        current_x = x
        print(" X%.4f" % x, end='')
    if y is not None:
        current_y = y
        print(" Y%.4f" % y, end='')
    if z is not None:
        print(" Z%.4f" % z, end='')
    print(" R%.4f" % retract, end='')
    print(" Q%.4f" % delta, end='')
    print()
    # FIXME: keep track of retract mode, set Z correctly here
    current_z = None


def drill_hog(diameter, retract, delta, z_drill, x0, y0, x1, y1, xy_finishing_allowance=None, z_finishing_allowance=None):

    """Drills as many evenly spaced holes as will fit in a rectangular
    grid, within the rectangle defined by (x0, y0) and (x1, y1).
    The specified rectangle describes the material contour, the holes
    will be inset from the edges by the drill's radius.

    If finishing_tolerance is specified, all the holes will stay at least
    that far away from the material contour the specified rectangle.
    If z_finishing_allowance is specified the holes will end that far
    above the specified drill depth."""

    print()
    print("; drill hog")

    radius = diameter/2.0

    min_x = min(x0, x1)
    max_x = max(x0, x1)

    min_y = min(y0, y1)
    max_y = max(y0, y1)

    if xy_finishing_allowance != None:
        min_x = min_x + xy_finishing_allowance
        max_x = max_x - xy_finishing_allowance
        min_y = min_y + xy_finishing_allowance
        max_y = max_y - xy_finishing_allowance

    if z_finishing_allowance != None:
        z_drill = z_drill + z_finishing_allowance

    x_range = max_x - min_x
    y_range = max_y - min_y

    num_in_x = int(math.floor(x_range / diameter))
    num_in_y = int(math.floor(y_range / diameter))

    min_x = min_x + radius
    max_x = max_x - radius

    min_y = min_y + radius
    max_y = max_y - radius

    x_range = x_range - diameter
    y_range = y_range - diameter

    for x_index in range(0, num_in_x):
        if num_in_x > 1:
            x = min_x + ((x_index / float(num_in_x - 1)) * x_range)
        else:
            x = min_x + (x_range / 2.0)

        for y_index in range(0, num_in_y):
            if num_in_y > 1:
                y = min_y + ((y_index / float(num_in_y - 1)) * y_range)
            else:
                y = min_y + (y_range / 2.0)

            g83(x=x, y=y, z=z_drill, delta=delta, retract=retract)

    print()


def z_path(path, depth_of_cut, z_start, z_top_of_work, z_target):

    """This function traverses a path (a list of waypoints), cutting a
    little deeper on each pass.  The waypoints are (X, Y) coordinates.
    The motion is this:

        1. Set Z to z_start.

        2. If z_top_of_work is below z_start, set Z level to z_top_of_work
           and feed down to Z (otherwise don't move the controlled point).

        3. Reduce Z by depth_of_cut, but not below z_target.

        4. Feed to each waypoint in path, in order starting with the
           first and ending with the last.

        5. After arriving at the last waypoint, if Z is not yet down to
           z_target: feed to the first waypoint while ramping down by
           depth_of_cut (but not below z_target), then go back to step
           4 for another trip around the path at this Z level.

        6. After reaching step 5 with Z at z_target, feed back to the
           first waypoint while keeping Z at the z_target level, thereby
           cutting away the ramp left by the previous iteration.


    The first move of this function is to the first waypoint in the
    path, at a Z level that's depth-of-cut below the lower of z_start
    and z_top_of_material (but not below z_target).  If you position
    the cutter above the *last* waypoint in the path, you'll get a nice
    consistent ramp down to the first waypoint each time around the path.

    When the function returns the controlled point is once again at the
    first waypoint in the path, all the way down at Z=z_target."""

    z = z_start

    if z > z_top_of_work:
        z = z_top_of_work
        g1(z = z)

    while z > z_target:
        z = z - depth_of_cut
        if z < z_target:
            z = z_target

        for waypoint in path:
            g1(x=waypoint['x'], y=waypoint['y'], z=z)

    # Cut away the last ramp we left behind.
    g1(**path[0])


def z_path2(path, depth_of_cut, z_target):

    """This function traverses a path (a list of Line, ArcCW, and ArcCCW
    objects), cutting a little deeper on each pass.

    z_path2() has a local variable named "Z" that tracks the Z level
    of the current pass.  On entry to the function it is initialized
    to gcoder's current Z position.  The Z variable overrides any Z
    coordinates specified in the path.

    The motion is this:

        1. Initialize the local variable Z to gcoder's current Z
           coordinate.

        2. Reduce Z by depth_of_cut, but not below z_target.

        3. Feed to each waypoint in path, in order starting with the
           first and ending with the last.

        4. After arriving at the last waypoint, if Z is not yet down to
           z_target, go to step 2.

        5. After reaching step 4 with Z at z_target, feed back to the
           first waypoint while keeping Z at the z_target level, thereby
           cutting away the ramp left by the previous iteration.

    The first move of this function is to the first waypoint in the path,
    at a Z level that's depth-of-cut below the starting Z level (but not
    below z_target).  If you position the cutter at the *last* waypoint
    in the path, at the start-of-material Z level, you'll get a nice
    consistent ramp down to the first waypoint each time around the path.

    When the function returns the controlled point is once again at the
    first waypoint in the path, all the way down at Z=z_target."""

    def handle_item(item):
        if type(item) is line:
            g1(x=item.x, y=item.y, z=z)
        elif type(item) is arc_cw:
            g2(x=item.x, y=item.y, z=z, i=item.i, j=item.j, p=item.p)
        elif type(item) is arc_ccw:
            g3(x=item.x, y=item.y, z=z, i=item.i, j=item.j, p=item.p)
        else:
            raise TypeError('z_path2() only accepts line(), arc_cw(), and arc_ccw() objects')

    z = current_z

    # Shrink depth_of_cut so all passes are equally deep, instead of
    # letting the final pass be "whatever's left over".
    z_range = current_z - z_target
    num_passes = math.ceil(float(z_range) / depth_of_cut)
    depth_of_cut = z_range / num_passes

    while not close_enough(z, z_target):
        z = z - depth_of_cut
        if z < z_target:
            z = z_target

        for item in path:
            handle_item(item)

    # Cut away the last ramp we left behind.
    handle_item(path[0])


def helix_hole(x, y, z_retract, z_start, z_bottom, diameter, doc):

    """This function helix-mills a hole.  The motion is this:

        1. Rapid to Z=z_retract.

        2. Rapid to the vincinity of (X, Y).

        3. Rapid to Z=z_start.

        4. Helix down to Z=z_bottom, descending not more than Z=doc
           per revolution.

        5. One more full circle at Z=z_bottom, to flatten the floor.

        6. Feed to the center of the hole and up off the floor a
           little bit.

        7. Rapid up to Z=z_retract."""

    r = diameter / 2.0

    z_range = z_start - z_bottom
    full_circles = math.ceil(z_range / doc)

    absolute_arc_centers()

    # get in position for the cut
    g0(z=z_retract)
    g0(x=x+r, y=y)
    g0(z=z_start)

    # helix down, then flatten the bottom
    g2(x=x+r, y=y, z=z_bottom, p=full_circles, i=x, j=y)
    g2(x=x+r, y=y, z=z_bottom, i=x, j=y)

    # extract the tool from the work
    g1(x=x, y=y, z=z_bottom + 0.025)
    g0(z=z_retract)


def saw_square(x_start, y_start, z_start, x_end, y_end, z_end, max_doc, rapid_plunge=True, final_retract=True):

    """Cuts back and forth between (X=x_start, Y=y_start) and (X=x_end,
    Y=y_end), plunging Z down (rapid or feed) at the end of each pass.

    The actual depth of cut may be reduced a little from max_doc to
    achieve equal depth of cut on each pass, while minimizing the number
    of passes.

    Upon return the tool will be positioned at either (X=x_start,
    Y=y_start) or at (X=x_end, Y=y_end), and at either Z=z_start (if
    final_retract is True) or Z=z_end (if final_retract is False).

    Motion:

        Initial Motion:

            Rapid to X=x_start, Y=y_start.

            Spindle on.

            Rapid to Z=z_start.

        Cycle:

            Plunge Z down by actual_doc, but not below z_end (rapid or
            feed, determined by rapid_plunge).

            Feed to X=x_end, Y=y_end.

            If Z is at z_end, goto Done.

            Plunge Z down by actual_doc, but not below z_end (rapid or
            feed, determined by rapid_plunge).

            Feed to X=x_start, Y=y_start.

            If Z is at z_end, goto Done.

            Goto Cycle.

        Done:

            If final_retract is True, rapid to Z=z_start."""

    global epsilon

    z_range = z_start - z_end
    num_passes = math.ceil(z_range / max_doc)
    doc = z_range / num_passes

    g0(x=x_start, y=y_start)

    spindle_on();

    z = z_start
    g0(z=z)

    while not close_enough(z, z_end):
        z = z - doc
        if z < z_end:
            z = z_end
        if rapid_plunge:
            g0(z=z)
        else:
            g1(z=z)
        g1(x=x_end, y=y_end)

        if not close_enough(z, z_end):
            z = z - doc
            if z < z_end:
                z = z_end
            if rapid_plunge:
                g0(z=z)
            else:
                g1(z=z)
            g1(x=x_start, y=y_start)

    if final_retract:
        g0(z=z_start)

