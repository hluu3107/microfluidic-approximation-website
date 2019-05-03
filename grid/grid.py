import math
import copy
from .gradient import *
from .helper import *

class Grid:	
	def __init__(self,size,nin,nout,nEdge,w,l,diffCoeff,matrix,initV,initC):
		self.size = size
		self.nIn = nin
		self.nOut = nout
		self.nNode = int(size * size + nin + nout)
		self.nEdge = int(nEdge)
		self.w = w
		self.l = l		
		self.diffCoeff = diffCoeff
		self.initV = initV
		self.adjMatrix = matrix
		self.initC = initC
		self.concentration = {}
		self.velocity = {}		
		self.pressure = []
		self.nodeClassification = {}
		self.splitList = {}
		self.tol = 1e-9

	def solveFlow(self):
		dim = self.nNode + self.nEdge
		#print(f'nEdge {self.nEdge} nNode: {self.nNode}')
		m1 = np.zeros([dim,dim])
		v1 = np.zeros([dim])
		vmap = {}
		count = self.nNode
		for node,neighbors in self.adjMatrix.items():
			for n in neighbors:
				if n > node:
					#print(f'vmap {count}: {node},{n}')
					vmap[(node,n)] = count
					count = count + 1

		#flow conservation eq
		for node,neighbors in self.adjMatrix.items():
			#outlets
			if node in range(self.nNode-self.nOut+1,self.nNode+1):
				m1[node-1,node-1] = 1
				continue
			#node with no edge
			if not neighbors:
				m1[node-1,node-1] = 1
			
			for n in neighbors:
				if n > node:
					m1[node-1,vmap[(node,n)]] = 1
				else:
					m1[node-1,vmap[(n,node)]] = -1				
			count = count+1

		#inlets
		for i in range(0,self.nIn):
			v1[i] = self.initV[i]

		resistant = 1.068
		#pressure eq
		for (u,v),num in vmap.items():
			m1[num,u-1]=1
			m1[num,v-1]=-1
			m1[num,num]=-resistant	
		# #print eq
		# for i in range(dim):
		# 	str = (f"Eq {i}: ")
		# 	for j in range(dim):
		# 		if m1[i,j]!=0:
		# 			str = str +(f"{m1[i,j]:.2f} X{j} ")
		# 	str = str + (f"= {v1[i]}")
		# 	print(str)
		result = np.linalg.solve(m1,v1)
		#store pressure result
		for i in range(0,self.nNode):
			self.pressure.append(result[i])
		#store velocity result
		for (u,v),num in vmap.items():
			self.velocity[(u,v)] = result[num]
			self.velocity[(v,u)] = -result[num]
		
		self.nodeClassification = self.classifyNode()

	def solveConcentration(self):
		w = self.w			
		nodeList = [n for n in range(1,self.nNode+1)]	

		#set up inlets: 1:5 c1=1, 2:8 c2=0
		for i in range(1,self.nIn+1):
			self.concentration[i] = self.initC[i-1]
			#print(f'Remove {i} inlet')
			nodeList.remove(i)
		splitList = self.splitList
		count = 0
		
		while(len(nodeList)>0):
		#while count < 2:
			count = count + 1
			#for node,neighbors in self.adjMatrix.items():
			for node in nodeList:
				if node in self.concentration:
			 		nodeList.remove(node)
				else:					
					#print(f'CALCULATE {node}')
					nodeGradient = self.getNodeGradient(node,splitList)
					#self.concentration[node] = nodeGradient
					#print(f'Set {node} to {nodeGradient}')
				
	def getNodeGradient(self,node,splitList,splitNode=0):				
		classificationList = self.nodeClassification[node]
		nodeType = classificationList[0]	
		inNode = classificationList[1]
		outNode = classificationList[2]
		sub_length = 0.8
		start_length = 0.2
		end_length = 0.4
		#print(f'	GET {node} + {nodeType}')
		if node in self.concentration and nodeType!='split' and nodeType!='mix':
			#print(f'	get gradient of {node}: {self.concentration[node]}')
			return self.concentration[node]		
		elif node in self.concentration and (nodeType=='split' or nodeType=='mix') and splitNode!=0:			
			if (node,splitNode) not in splitList:					
				#calculate split				
				inGrad = self.concentration[node]
				#print(f'	Calculate split of {node}')
				#flip output order
				if len(outNode)==2:					
					if ((outNode[0]==node-self.size) and (outNode[1]==node+1)) or ((outNode[0]==node-1) and (outNode[1]==node-self.size)):
						outNode[0],outNode[1] = outNode[1],outNode[0]					
				if len(outNode)==3:				
					if ((outNode[0]==node-self.size) and (outNode[1]==node+self.size)) and outNode[2]==node+1:
						outNode[0],outNode[1],outNode[2] = node+self.size,node+1,node-self.size		
				outVel = [abs(self.velocity[(node,out)]) for out in outNode]
				outGrad = calculateSplit(inGrad,outVel,self.w)
				for i in range(len(outGrad)):
					splitList[(node,outNode[i])] = outGrad[i]
					#print(f'{node}-{outNode[i]}: {outGrad[i]}')
			#print(f'	get gradient of {node} from splitList: {splitList[(node,splitNode)]}')
			return splitList[(node,splitNode)]
		
		#no inflow dead node
		if len(inNode) == 0:
			result = Gradient(0,0,0,self.w,self.w)
		#only one in. Calculate straight
		elif len(inNode)==1:			
			#print(f'straight from {inNode} to {node}')
			inNodeGrad = self.getNodeGradient(inNode[0],splitList,node)
			inNodeType = self.nodeClassification[inNode[0]][0]			
			
			if inNode[0] not in self.concentration:
				#print(f'	Set {inNode[0]} to {inNodeGrad}')
				self.concentration[inNode[0]] = inNodeGrad
			
			if inNodeType == 'split' or inNodeType == 'mix':
				inNodeOut = self.nodeClassification[inNode[0]][2]
				if (inNode[0],node) not in splitList:
					#print(f'	Calculate split of {inNode[0]} in straight')
									
					if len(inNodeOut)==2:						
						if ((inNodeOut[0]==inNode[0]-self.size) and (inNodeOut[1]==inNode[0]+1)) or (inNodeOut[0]==inNode[0]-1 and inNodeOut[1]==inNode[0]-self.size):
							inNodeOut[0],inNodeOut[1] = inNodeOut[1],inNodeOut[0]
					if len(inNodeOut)==3:				
						if ((inNodeOut[0]==inNode[0]-self.size) and (inNodeOut[1]==inNode[0]+self.size)) and inNodeOut[2]==inNode[0]+1:
							inNodeOut[0],inNodeOut[1],inNodeOut[2] = inNode[0]+self.size,inNode[0]+1,inNode[0]-self.size							
					
					outVel = [abs(self.velocity[(inNode[0],out)]) for out in inNodeOut]
					outGrad = calculateSplit(inNodeGrad,outVel,self.w)
					for i in range(len(outGrad)):
						splitList[(inNode[0],inNodeOut[i])] = outGrad[i]
				inNodeGrad = splitList[(inNode[0],node)]
			
			length = self.l
			if inNodeType == 'split' or inNodeType == 'mix' or inNodeType == 'join':
				length = sub_length + self.l - start_length - end_length
			dT = calculateTime(length,self.velocity[(inNode[0],node)])
			result = calculateStraight(inNodeGrad,dT,self.diffCoeff,self.w)
		#2,3 inflow. Join			
		else:
			inNodeGrads = []
			if len(inNode)==3:
				#if join 3 -1,-size,+size
				if inNode[2]==node+self.size:
					inNode[0],inNode[1] = inNode[1],inNode[0]
			elif len(inNode)==2 and len(outNode)==1:
				if inNode[1]==node+self.size and outNode[0]==node+1:
					inNode[0],inNode[1] = inNode[1],inNode[0]

			inVel = [abs(self.velocity[(n,node)]) for n in inNode]			
			for k in range (len(inNode)):
				n = inNode[k]
				#after getting all input, calculate straight then join
				inGrad = self.getNodeGradient(n,splitList,node)
				nType = self.nodeClassification[n][0]	
				
				if n not in self.concentration:
					#print(f'	Set {n} to {inGrad}')
					self.concentration[n] = inGrad

				if nType == 'split' or nType == 'mix':
					inNodeOut = self.nodeClassification[n][2]
					if (n,node) not in splitList:
						#print(f'	Calculate split of {n} in join')
						if len(inNodeOut)==2:
							if (inNodeOut[0]==n-self.size and inNodeOut[1]==n+1) or (inNodeOut[0]==n-1 and inNodeOut[1]==n-8):
								inNodeOut[0],inNodeOut[1] = inNodeOut[1],inNodeOut[0]							
						if len(inNodeOut)==3:				
							if ((inNodeOut[0]==n-self.size) and (inNodeOut[1]==n+self.size)) and inNodeOut[2]==n+1:
								inNodeOut[0],inNodeOut[1],inNodeOut[2] = n+self.size,n+1,n-self.size
						outVel = [abs(self.velocity[(n,out)]) for out in inNodeOut]
						outGrad = calculateSplit(inGrad,outVel,self.w)
						for i in range(len(outGrad)):
							splitList[(n,inNodeOut[i])] = outGrad[i]
					inGrad = splitList[(n,node)]				
				
				length = self.l
				if nType == 'split' or nType == 'mix' or nType == 'join':
					length = sub_length + self.l - start_length - end_length
				
				dT = calculateTime(length,inVel[k])
				inNodeAfter = calculateStraight(inGrad,dT,self.diffCoeff,self.w)
				inNodeGrads.append(inNodeAfter)
					
			# print(f'Join from {inNode} to {node}')
			# for grad in inNodeGrads:
			# 	print(grad)
			result = calculateJoin(inNodeGrads,inVel,self.w)
		if node not in self.concentration:
			#print(f'	Set {node} to {result}')
			self.concentration[node] = result			
		return result	
		
	def classifyNode(self):
		result = {}
		for node,neighbors in self.adjMatrix.items():
			#print(f'node {node}: {neighbors}')
			if node <= self.nIn:
				resultList = ['inlet',[],[neighbors[0]]]
			elif node > self.nNode - self.nOut:
				resultList = ['outlet',[neighbors[0]],[]]				
			else:
				nin = []; nout = []; nodeType = ''
				for n in neighbors:
					if abs(self.velocity[(node,n)]) <=1e-9:
						continue;
					elif self.velocity[(node,n)]>= 0: 
						nout.append(n)
					else: 
						nin.append(n)
				if not nin and not nout:
					nodeType = 'deadnode'
				elif len(nin) + len(nout)==1:
					nodeType = 'deadend'
				elif (nin and not nout) or (nout and not nin):
					nodeType = 'dead'
				elif len(nin)==1 and len(nout)==1:
					nodeType = 'straight'
				elif len(nin)==1 and nout:
					nodeType = 'split'
				elif len(nout)==1 and nin:
					nodeType = 'join'
				elif len(nin) > 1 and len(nout) > 1:
					nodeType = 'mix'
				else:
					nodeType = 'error'
				resultList = [nodeType,nin,nout]
				#print(f'node {node} is {nodeType}')
			result[node] = resultList			
		return result

def calculateStraight(inGrad, dT, diffCoeff,w):	
	#if shape 1
	if inGrad.a == inGrad.b:
		return inGrad
	result = Gradient(inGrad.a,inGrad.b,inGrad.d1,inGrad.d2,w)
	shape = inGrad.shape()
	area = inGrad.calculateArea()
	lp_diff = 2*math.sqrt(diffCoeff*abs(dT))
	#if shape 3 has both head and tail 
	if shape == 3:		
		d1p = inGrad.d1-lp_diff
		d2p = inGrad.d2+lp_diff
		if d1p>=0 and d2p<=w:
			result.d1 = d1p
			result.d2 = d2p
		#not  in correct form
		elif d1p<0 and (d2p <= w or (d2p-w)<abs(d1p)):
			remain = abs(d1p)
			t = inGrad.d1**2/(4*diffCoeff)
			newT = dT - t
			newInGrad = Gradient(inGrad.a,inGrad.b,0,d2p-remain,w)
			#print(f'Straight Not in correct form 1')
			newResult = calculateStraight(newInGrad,newT,diffCoeff,w)
			result = newResult
		else: #d2p > w and (d1p>=0 or (d2p-w)>=abs(d1p))
			remain = d2p-w
			t = (w-inGrad.d2)**2/(4*diffCoeff)
			newT = dT - t
			newInGrad = Gradient(inGrad.a,inGrad.b,d1p+remain,w,w)
			#print(f'Straight Not in correct form 2')
			newResult = calculateStraight(newInGrad,newT,diffCoeff,w)
			result = newResult
	#if shape 2 linear line
	elif shape == 2:
		m = lp_diff/2
		ap = inGrad.a+(m*(inGrad.b-inGrad.a))/(w+2*m)
		bp = inGrad.b-(m*(inGrad.b-inGrad.a))/(w+2*m)
		if ap >= bp:
			result.a = ap
			result.b = bp			
		else:
			#not in correct form ap < bp. return balance form straight line
			balance = (inGrad.a+inGrad.b)/2
			result.a = balance
			result.b = balance
			#print(f'Straight Not in correct form 3')		
	#if shape 4
	elif shape == 4:
		d1p = inGrad.d1 - lp_diff		
		if d1p >=0:
			bp = 2*(area-inGrad.a*d1p)/(w-d1p)-inGrad.a
			result.b = bp
			result.d1 = d1p
		else:
			#not in correct form
			t = inGrad.d1**2/(4*diffCoeff)
			newT = dT - t		
			bp = 2*area/w-inGrad.a
			newInGrad = Gradient(inGrad.a,bp,0,w,w)
			#print(f'Straight Not in correct form 4')
			newResult = calculateStraight(newInGrad,newT,diffCoeff,w)
			result = newResult
	elif shape == 5:
		d2p = inGrad.d2 + lp_diff
		if d2p <=w:
			ap = 2*(area-inGrad.b*(w-d2p))/d2p - inGrad.b
			result.a = ap
			result.d2 = d2p
		else:
			#not in correct form
			t = (w-inGrad.d2)**2/(4*diffCoeff)
			newT = dT - t
			ap = 2*area/w - inGrad.b
			newInGrad = Gradient(ap,inGrad.b,0,w,w)
			#print(f'Straight Not in correct form 5')
			newResult = calculateStraight(newInGrad,newT,diffCoeff,w)
			result = newResult

	totalArea = inGrad.calculateArea()
	resultArea = result.calculateArea()	
	if abs(resultArea-totalArea) > 1e-9:
		print(f'STRAIGHT not correct. Old area = {totalArea:.6f} New area = {resultArea:.6f}')		
	return result

def calculateSplit(inGrad,outVel,w):
	result = []
	shape = inGrad.shape()
	area = inGrad.calculateArea()		
	#if shape 1
	if shape == 1:
		for i in range(len(outVel)):
			result.append(copy.copy(inGrad))
		return result
	sumV = sum(v for v in outVel)
	ratio = []
	for v in outVel:
		ratio.append(abs(v)/sumV)
	dmid1 = w*ratio[0]
	cmid1 = inGrad.getConcentration(dmid1)
	#split 2
	if len(outVel)==2:	
		newg1 = Gradient(inGrad.a,cmid1,0,w,w)
		newg2 = Gradient(cmid1,inGrad.b,0,w,w)
		#if shape 2 no modification. If not need to check where mid line fall into
		if shape!=2:
			if dmid1 <= inGrad.d1:
				#case mid line before d1
				#print(f'Split 2 Case 1')				
				newg2.d1 = (inGrad.d1-dmid1)/ratio[1]
				newg2.d2 = (inGrad.d2-dmid1)/ratio[1]
			elif dmid1 >= inGrad.d2:
				#case mid line after d2
				#print(f'Split 2 Case 2')
				newg1.d1 = inGrad.d1/ratio[0]
				newg1.d2 = inGrad.d2/ratio[0]
			else: 
				#case mid line in between d1 and d2
				#print(f'Split 2 Case 3')
				newg1.d1 = inGrad.d1/ratio[0]
				newg2.d2 = (inGrad.d2-dmid1)/ratio[1]
		result.extend([newg1,newg2])
	#split 3
	elif len(outVel)==3:
		dmid2 = w*(1-ratio[2])
		cmid2 = inGrad.getConcentration(dmid2)
		newg1 = Gradient(inGrad.a,cmid1,0,w,w)
		newg2 = Gradient(cmid1,cmid2,0,w,w)
		newg3 = Gradient(cmid2,inGrad.b,0,w,w)		
		#if shape 2 no modification. If not need to check where mid line fall into
		if shape!=2:
			#case mid line 1 before d1. out1 is done
			if dmid1 <= inGrad.d1:
				if dmid2 <= inGrad.d1:
					#case mid2 before d1 need to fix out3
					#print(f'Case 1')
					newg3.d1 = (inGrad.d1-dmid2)/ratio[2]
					newg3.d2 = (inGrad.d2-dmid2)/ratio[2]
				elif dmid2 >= inGrad.d2:
					#case mid line 2 after d2 need to fix out2
					#print(f'Case 2')
					newg2.d1 = (inGrad.d1-dmid1)/ratio[1]
					newg2.d2 = (inGrad.d2-dmid1)/ratio[1]
				else:
					#print(f'Case 3')
					#case mid line 2 between d1 and d2. fix out2 and out3
					newg2.d1 = (inGrad.d1-dmid1)/ratio[1]
					newg3.d2 = (inGrad.d2-dmid2)/ratio[2]
			#case mid line 1 after d2. out2 and out3 is done
			elif dmid1 >= inGrad.d2:				
				#print(f'Case 4')
				newg1.d1 = inGrad.d1/ratio[0]
				newg1.d2 = inGrad.d2/ratio[0]
			#case mid line 1 between d1 and d2
			else:
				newg1.d1 = inGrad.d1/ratio[0]
				if dmid2 <= inGrad.d2:
					#print(f'Case 5')
					#case mid2 between d1 and d2 need to fix out3
					newg3.d2 = (inGrad.d2-dmid2)/ratio[2]
				else:
					#print(f'Case 6')
					#case mid2 bafter d2 fix out2
					newg2.d2 = (inGrad.d2-dmid1)/ratio[1]
		result.extend([newg1,newg2,newg3])
		
	newarea = 0;
	for i in range(len(result)):
		newarea = newarea + result[i].calculateArea()*ratio[i]
	if abs(newarea - area) > 1e-6:				
		print(f'SPLIT not correct original Area: {area:.6f} new area: {newarea:.6f}')
	return result

def calculateJoin(inGrad,inVel,w):	
	sumV = sum(v for v in inVel)
	totalArea = 0
	for i in range (len(inVel)):
		totalArea = totalArea + inGrad[i].calculateArea()*(abs(inVel[i]/sumV))
	
	inGradScale = copy.copy(inGrad)
	#scale inGrad
	for i in range (len(inVel)):
		ratio = abs(inVel[i])/sumV		
		inGradScale[i].d1 = inGrad[i].d1*ratio
		inGradScale[i].d2 = inGrad[i].d2*ratio
		inGradScale[i].w = inGrad[i].w*ratio

	allPoints,internalPoints,outerPoints = getPoints(inGradScale,w)	
	
	#if internalPoints size is 1
	if len(internalPoints) > 0:
		result = joinCase2(outerPoints,totalArea,w)
	#print(f'len all points {len(allPoints)} and len internalPoints {len(internalPoints)}')
	#if internalPoints is empty the join shape is already correct
	if not internalPoints and len(allPoints) <= 4 and len(allPoints)>=2:
		#print(f'	Join 3')
		if len(allPoints)==2:
			#type 1,2
			result = Gradient(allPoints[0].y,allPoints[1].y,
							allPoints[0].x,allPoints[1].x,w)
		elif len(allPoints)==3:
			#type 4 or 5
			d1 = allPoints[0].x
			d2 = allPoints[2].x
			if allPoints[1].y == allPoints[0].y:
				d1 = allPoints[1].x
			else:
				d2 = allPoints[1].x
			result = Gradient(allPoints[0].y,allPoints[2].y,
							d1,d2,w)
		else:
			#type 3
			result = Gradient(allPoints[0].y,allPoints[3].y,
							allPoints[1].x,allPoints[2].x,w)	
	
	resultArea = result.calculateArea();
	
	if abs(resultArea-totalArea) > 1e-9:
		print(f'JOIN not correct. Old area = {totalArea:.6f} New area = {resultArea:.6f}')
	
	return result

def joinCase2(outerPoints,area,w):
	tol = 1e-9
	a = outerPoints[0].y; b = outerPoints[1].y
	d1 = outerPoints[0].x; d2 = outerPoints[1].x	
	newGrad = Gradient(a,b,d1,d2,w)
	newArea = newGrad.calculateArea()
	if abs(area-newArea) <= 1e-9:
		return newGrad
	if area < newArea:
		newGrad.d2 = w
		newArea = newGrad.calculateArea()		
		if area < newArea: 
			#print(f'join case 2.1')
			#determine new d2
			d2p = (area + (a+b)*d1/2 - a*d1 - b*w) / ((a+b)/2 - b);
			newGrad.d2 = d2p
		elif area > newArea:
			#print(f'join case 2.2')
			#determine new b
			if abs(w-d1) < 1e-9:
				bp = 2*area/w - a
			else:
				bp = (2*(area-a*d1))/(w-d1)-a
			newGrad.b = bp
	elif area > newArea:
		newGrad.d1 = 0
		newArea = newGrad.calculateArea()
		if area > newArea:
			#print(f'join case 2.3') 
			#determine new d1
			d1p = (area-b*(w-d2)-(a+b)*d2/2)/(a-(a+b)/2)
			newGrad.d1 = d1p
		elif area < newArea:
			#determine new a
			#print(f'join case 2.4')
			if abs(w-d1) < 1e-9:
				ap = 2*area/w -b
			else:
				ap = (2*(area-b*(w-d2))/d2)-b
			newGrad.a = ap
	#print(f'Join case 2 result: {newGrad}')
	return newGrad

def getPoints(inGrad,w):
	allPoints = []
	midLine = 0
	tol = 1e-9
	for grad in inGrad:
		if abs(grad.d1) <= tol:
			grad.d1 = 0
		if abs(grad.d2-w) <=tol:
			grad.d2 = w
		if(abs(grad.a)) <= tol:
			a = 0
		elif(abs(grad.a-1)) <= tol:
			a = 1
		if(abs(grad.b)) <=tol:
			b = 0
		elif(abs(grad.b-1)) <=tol:
			b = 1
	for grad in inGrad:
		points = [Point(midLine,grad.a),Point(grad.d1+midLine,grad.a),
				  Point(grad.d2+midLine,grad.b),Point(grad.w+midLine,grad.b)]
		for p in points:
			if p not in allPoints:
				allPoints.append(p)
		midLine = midLine + grad.w
	#remove points in the same line
	simplifyPointList(allPoints)	
	
	internalPoints = []	
	for i in range(1,len(allPoints)-1):
		if allPoints[i].y!=allPoints[0].y and allPoints[i].y!=allPoints[-1].y:
			internalPoints.append(allPoints[i])
	
	outerPoints = list_diff(allPoints,internalPoints)
	if len(outerPoints) > 2 and outerPoints[0].y == outerPoints[1].y:
		outerPoints.remove(outerPoints[0])
	if len(outerPoints) > 2 and outerPoints[-1].y == outerPoints[-2].y:
		outerPoints.remove(outerPoints[-1])
	return allPoints,internalPoints, outerPoints

def simplifyPointList(allPoints):
	#check every 3 points if it's in the same line remove the mid point
	remove_idx = []
	for i in range(len(allPoints)-2):		
		if np.all(abs(allPoints[i].x - allPoints[i-1].x) < 1e-9) and np.all(abs(allPoints[i].y - allPoints[i-1].y) < 1e-9):
			if i+1 not in remove_idx:
				remove_idx.append(i+1)
		else:
			slope1 = getSlope(allPoints[i],allPoints[i+1])
			slope2 = getSlope(allPoints[i+1],allPoints[i+2])
			if slope1==None:
				slope1 = math.pi/2
			if slope2 == None:
				slope2 = math.pi/2
			if abs(slope1-slope2)<1e-9:
				if i+1 not in remove_idx: 
					remove_idx.append(i+1)
	for i in range(len(remove_idx)):
		del allPoints[remove_idx[i]-i]		
