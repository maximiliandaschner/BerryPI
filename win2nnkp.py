#!/usr/bin/env python
import sys
from datetime import datetime
import numpy
import functools # needed for functools.reduce()
import argparse # parse line arguments

def write_date(f):
    t = datetime.now()
    f.write('File written on ')
    f.write(t.strftime('%d%b%Y at %H:%M:%S'))
    f.write('\n\n')

def write_calc_only_A(f): # TODO
    f.write('calc_only_A  :  F\n\n')

def write_real_lattice(f, real_lattice):
    f.write('begin real_lattice\n')
    for i in range(3):
        a = real_lattice[i]
        f.write(' {0:>11.7f} {1:>11.7f} {2:>11.7f}\n'.format(*a))
    f.write('end real_lattice\n\n')

def write_recip_lattice(f, recip_lattice):
    f.write('begin recip_lattice\n')
    for i in range(3):
        a = recip_lattice[i]
        f.write(' {0:>11.7f} {1:>11.7f} {2:>11.7f}\n'.format(*a))
    f.write('end recip_lattice\n\n')

def write_kpoints(f, kpoints):
    f.write('begin kpoints\n')
    f.write('{0:>6d}\n'.format(len(kpoints)))
    for p in kpoints:
        f.write(' {0:>13.8f} {1:>13.8f} {2:>13.8f}\n'.format(*p))

    f.write('end kpoints\n\n')

def write_projections(f): # TODO
    f.write('begin projections\n')
    f.write('end projections\n\n')

def write_nnkpts(f, nnkpts,wCalc):
    neighbours_per_kpoint = 3 # x, y, z

    f.write('begin nnkpts\n')
    if wCalc:
        f.write('{0:4d}\n'.format(1)) # one neightbor for Weyl k-path
    else:
        f.write('{0:4d}\n'.format(neighbours_per_kpoint))
    for p in nnkpts:
        f.write(' {0:5d} {1:5d}    {2:3d} {3:3d} {4:3d}\n'.format(*p))
    f.write('end nnkpts\n\n')

def write_exclude_bands(f): # TODO
    f.write('begin exclude_bands\n')
    f.write('{0:4d}\n'.format(0))
    f.write('end exclude_bands\n')

# Turn `line`, a string of a `delimiter` delimited list of `T`s, into a list of `T`s.
parse_line_list = lambda line, delimiter, T : [T(y) for y in [x.strip() for x in line.strip().split(delimiter)] if y] 

def calculate_nnkpts(D,wCalc,wTranslDir,nkpt):
    '''Calculates neighbours pairs for all paths. 
        D - k-mesh (#,#,#)
        wCalc - Logical var to indicate Weyl path calculation (True/False)
        wTranslDir - Direction for k(1)+G[dir] at the end of the loop.
        nkpt - number of k-points in the list
    '''

    # Helper functions
    product = lambda l : functools.reduce(lambda x,y : x*y, l, 1)
    vector_add = lambda v1,v2 : [x + y for x, y in zip(v1,v2)]
    permute = lambda v,P: [v[i] for i in P]
    linear_index = lambda v,D: sum(c*i for i,c in zip(v,[product(D[:i]) for i in range(len(D))]))
    
    def wrap_vector(v,d,D):
        # Put v in bounds of D
        # Return the new v and the G vector
    
        G = [0,0,0]
        for i, j in enumerate(d):
            # Wrap i at boundaries
            if j != 0:
                if v[i] < 0 or v[i] >= D[i]:
                    v[i] = v[i] % D[i]
                    G = d
    
        return v,G
    
    # Determine the neighbours defining each path in provided direction
    P = [2, 1, 0] # Permutation for index calculation
    directions = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    nnkpts = []
    for a in range(D[0]):
        for b in range(D[1]):
            for c in range(D[2]):
                for d in directions:
                    # Build k-point and neighbour vectors
                    v = [a, b, c]
                    v_neighbour, G = wrap_vector(vector_add(v, d), d, D)
    
                    # Get indices for vectors
                    i = linear_index(permute(v, P), permute(D, P)) + 1
                    i_neighbour = linear_index(permute(v_neighbour, P), permute(D, P)) + 1
    
                    # Remember neighbours
                    nnkpts.append((i, i_neighbour, G[0], G[1], G[2]))

    if wCalc: # alternative calculation for a k-path of point listed in order
        nnkpts = []
        for i in range(nkpt-1): # except for last k-point
            nnkpts.append((i+1, i+2, 0, 0, 0)) # list of NN kpt1 - kpt2, etc.
        if wTranslDir == 0:
            # last k-point is linked to the k(1)
            nnkpts.append((nkpt, 1, 0, 0, 0))
        elif wTranslDir == 1:
            # last k-point is linked to the k(1)+G[1]
            nnkpts.append((nkpt, 1, 1, 0, 0))
        elif wTranslDir == 2:
            # last k-point is linked to the k(1)+G[2]
            nnkpts.append((nkpt, 1, 0, 1, 0))
        elif wTranslDir == 3:
            # last k-point is linked to the k(1)+G[3]
            nnkpts.append((nkpt, 1, 0, 0, 1))
        else:
            raise ValueError(f'Error in win2nnkp wTranslDir={wTranslDir}, while expected one of [0,1,2,3]')

    return nnkpts

def parse_win_kpoints(f):
    # Find the start of the kpoints list
    while 'begin kpoints' not in f.readline():
        pass
    
    kpoints = []
    for line in f.readlines(): # OR python 3
        if 'end kpoints' in line:
            break
        kpoint = tuple(parse_line_list(line, ' ', float))
        kpoints.append(kpoint)

    return kpoints

def parse_win_mp_grid(f):
    for line in f.readlines(): # OR python 3
        if 'mp_grid' in line:
            # mp_grid :         A     B     C
            # Split in two by :, take second half
            return parse_line_list(line.split(':')[1], ' ', int)

def parse_win_unit_cell_cart(f):
    reciprocal = lambda a: numpy.transpose(6.28318*numpy.linalg.inv(a)) # [b1 b2 b3]^T = 2*pi*[a1 a2 a3]^-1

    real_lattice = numpy.zeros(shape=(3,3))
     
    # Find start of block
    while 'begin unit_cell_cart' not in f.readline():
        pass

    f.readline() # TODO unit line 

    # Read in 3 vectors
    for i in range(3):
        real_lattice[i] = parse_line_list(f.readline(), ' ', float)

    # Convert from Bohr to Angstrom
    real_lattice = real_lattice * 0.52917720859

    return real_lattice, reciprocal(real_lattice) 

def parse_win(case_name,spinLable):
    # define extension file
    ext = '.win' + spinLable
    file_name = case_name + ext

    f = open(file_name, 'r')
    real_lattice, recip_lattice = parse_win_unit_cell_cart(f)
    f.close()

    f = open(file_name, 'r')
    dimensions = parse_win_mp_grid(f)
    f.close()

    f = open(file_name, 'r')
    kpoints = parse_win_kpoints(f)
    f.close()

    return real_lattice, recip_lattice, dimensions, kpoints


if __name__ == "__main__":
    # Set up parser for line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("case",\
        help="WIEN2k case name",\
        nargs=1,\
        type=str)
    parser.add_argument("-up",\
        help="Spin polarized calculation (up component)",\
        action="store_true")
    parser.add_argument("-dn",\
        help="Spin polarized calculation (dn component)",\
        action="store_true")
    parser.add_argument("-w",\
        help="compute Berry phase along a specific (closed loop) k-path given "+\
            "in the case.klist file (used for topological Weyl semimetals "+\
            "and Wannier charge centers). "+\
            "First k(1) and last k(n) points in the case.klist file will be "+\
            "joined to form a closed loop k(1) -> k(2) -> ... -> k(n) -> k(1). "+\
            "The argument (optional) specifies when a periodic image of k(1) "+\
            "should be used. For example '-w 2' means the following path: "+\
            "k(1) -> k(2) -> ... -> k(n) -> k(1)+G[2], where G[2] is the second "+\
            "reciprocal lattice vector. By default we assume '-w 0', which implies "+\
            "that no translation is added at the end of the loop.",\
        nargs='?',\
        const=0,\
        choices=[0, 1, 2, 3],\
        type=int)
    args = parser.parse_args()
    # Assign line arguments parsed by "argparse"
    case_name = args.case[0] # WIEN2k case name
    print(f'case_name={case_name}')
    if args.up: # spin up
        spinLable = 'up'
        spCalc = True
    elif args.dn: # spin dn
        spinLable = 'dn'
        spCalc = True
    elif args.up and args.dn:
        print("wien2nnkp.py args=", args)
        raise ValueError("It seems that you try to combine spin '-up' and '-dn' argument in one call.")
    else:
        spinLable = "" # no spins
        spCalc = False
    wTranslDir = args.w # no k-path specified by default
    if wTranslDir == None:
        wCalc = False # no Weyl path by default
    else:
        wCalc = True

    # Parameters
    
    permutation = [2,1,0] # Permutation vector (changes "order" of dimensions)

    # Parse input
    real_lattice, recip_lattice, dimensions, kpoints = parse_win(case_name,spinLable)

    # Calculate nnkpts
    nnkpts = calculate_nnkpts(dimensions,wCalc,wTranslDir,len(kpoints))

    # Write output
    f = open(case_name + '.nnkp', 'w')

    write_date(f)
    write_calc_only_A(f) # TODO
    write_real_lattice(f, real_lattice)
    write_recip_lattice(f, recip_lattice)
    write_kpoints(f, kpoints)
    write_projections(f) # TODO
    write_nnkpts(f, nnkpts, wCalc)
    write_exclude_bands(f) # TODO

    f.close()
