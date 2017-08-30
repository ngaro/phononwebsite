#!/usr/bin/env python
# Copyright (c) 2015, Henrique Miranda
# All rights reserved.
#
# This file is part of the phononwebsite project
#
# Read phonon dispersion from quantum espresso
#
from pw import *
from phononweb import *
import numpy as np
from math import pi

class QePhonon(Phonon):
    """
    Class to read phonons from Quantum Espresso

    Input:
        prefix = prefix of the <prefix>.scf file where the structure is stored
                           the <prefix>.modes file that is the output of the matdyn.x or dynmat.x programs
    """
    def __init__(self,prefix,name,reps=(3,3,3),folder='.',highsym_qpts=None,reorder=True,scf=None,modes=None):
        self.prefix = prefix
        self.name = name
        self.reps = reps
        self.folder = folder
        self.highsym_qpts = highsym_qpts

        #read atoms
        if scf:   filename = "%s/%s"%(self.folder,scf)
        else :    filename = "%s/%s.scf"%(self.folder,self.prefix)
        self.read_atoms(filename)
        
        #read modes
        if modes: filename = "%s/%s"%(self.folder,modes)
        else :    filename = "%s/%s.modes"%(self.folder,self.prefix)
        self.read_modes(filename)
        

        #reorder eigenvalues
        if reorder:
            self.reorder_eigenvalues()
        self.get_distances_qpts()
        self.labels_qpts = None

    def read_modes(self,filename):
        """
        Function to read the eigenvalues and eigenvectors from Quantum Expresso
        """
        f = open(filename,'r')
        file_list = f.readlines()
        file_str  = "".join(file_list)
        f.close()

        #determine the numer of atoms
        nphons = max([int(x) for x in re.findall( '(?:freq|omega) \((.+)\)', file_str )])
        atoms = nphons/3

        #check if the number fo atoms is the same
        if atoms != self.natoms:
            print "The number of atoms in the <>.scf file is not the same as in the <>.modes file"
            exit(1)

        #determine the number of qpoints
        self.nqpoints = len( re.findall('q = ', file_str ) )
        nqpoints = self.nqpoints

        eig = np.zeros([nqpoints,nphons])
        vec = np.zeros([nqpoints,nphons,atoms,3],dtype=complex)
        qpt = np.zeros([nqpoints,3])
        for k in xrange(nqpoints):
            #iterate over qpoints
            k_idx = 2 + k*((atoms+1)*nphons + 5)
            #read qpoint
            qpt[k] = map(float, file_list[k_idx].split()[2:])
            for n in xrange(nphons):
                #read eigenvalues
                eig_idx = k_idx+2+n*(atoms+1)
                eig[k][n] = float(re.findall('=\s+([+-]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)',file_list[eig_idx])[1])
                for i in xrange(atoms):
                    #read eigenvectors
                    z = map(float,re.findall('([+-]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)',file_list[eig_idx+1+i]))
                    vec[k][n][i] = np.array( [complex(z[0],z[1]),complex(z[2],z[3]),complex(z[4],z[5])], dtype=complex )

        #the quantum espresso eigenvectors are already scaled with the atomic masses
        #if the file comes from dynmat.eig they are not scaled with the atomic masses
        #here we scale then with sqrt(m) so that we recover the correct scalling on the website
        #we check if the eigenvectors are orthogonal or not
        #for na in xrange(self.natoms):
        #    atomic_specie = self.atypes[na]-1
        #    atomic_number = self.atomic_numbers[atomic_specie]
        #    vectors[:,:,na,:,:] *= sqrt(atomic_mass[atomic_number])

        self.nqpoints     = len(qpt)
        self.nphons       = nphons
        self.eigenvalues  = eig#*eV/hartree_cm1
        self.eigenvectors = vec.view(dtype=float).reshape([self.nqpoints,nphons,nphons,2])
        self.qpoints      = qpt

        #convert to cartesian coordinates
        self.qpoints = car_red(self.qpoints,self.rec)
        return self.eigenvalues, self.eigenvectors, self.qpoints

    def read_atoms(self,filename):
        """ 
        read the data from a quantum espresso input file
        """
        pwin = PwIn(filename=filename)
        self.cell, self.pos, self.atom_types = pwin.get_atoms()
        self.cell = np.array(self.cell)*bohr_angstroem
        self.rec = rec_lat(self.cell)*2*pi
        self.pos = np.array(self.pos)
        self.atom_numbers = [atomic_numbers[x] for x in self.atom_types]
        self.atomic_numbers = np.unique(self.atom_numbers)
        self.chemical_symbols = np.unique(self.atom_types).tolist()
        self.natoms = len(self.pos)
        self.chemical_formula = self.get_chemical_formula()

        pos_type = pwin.atomic_pos_type.lower()
        if pos_type == "cartesian":
            #convert to reduced coordinates
            self.pos = car_red(self.pos,self.cell)
        elif pos_type == "crystal" or pos_type == 'alat':
            pass
        else:
            print "Coordinate format %s in input file not known"%pos_type
            exit(1)

