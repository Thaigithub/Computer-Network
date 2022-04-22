class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		try:
			self.file = open(filename, 'rb')
		except:
			raise IOError
		self.frameNum = 0
		self.frameList = []
		self.fast_forward = 0
		self.fast_backward = 0
		self.frameSeq = 0

	def fastForward(self):
		self.fast_forward += 1

	def fastBackward(self):
		self.fast_backward += 1


	def increaseFrame(self, numFrame):
		prevData = -1	# For case end of movie
		for i in range(numFrame):
			data = self.file.read(5)
			if data:
				frameLength = int(data)
				data = self.file.read(frameLength)
				self.frameNum += 1
				prevData = data
				if self.frameNum > len(self.frameList):
					self.frameList.append(frameLength)
			else:
				return prevData # Because read end of file
		return -1

	def decreaseFrame(self, numFrame):
		if numFrame >= self.frameNum:	# Backward to beginning of file
			self.file.seek(0, 0)
			self.frameNum = 0
		else:
			for i in range(numFrame):
				self.frameNum -= 1
				self.file.seek(-5 - self.frameList[self.frameNum], 1)

	def nextFrame(self):
		""" Fast forward """
		if self.fast_forward > 0:
			res = self.increaseFrame(self.fast_forward * 3 * 25)
			self.fast_forward = 0
			if res != -1:
				self.frameNum += 1
				return res

		""" Fast backward"""
		if self.fast_backward > 0:
			self.decreaseFrame(self.fast_backward * 3 * 25)
			self.fast_backward = 0

		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		if data:
			framelength = int(data)
			self.frameNum += 1
			# Read the current frame
			data = self.file.read(framelength)
			if self.frameNum > len(self.frameList):
				self.frameList.append(framelength)

			self.frameSeq += 1

		return data

	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum

	def frameSequence(self):
		"""Get frame sequence."""
		return self.frameSeq


