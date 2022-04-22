
import os
from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket
from datetime import timedelta

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	DESCRIBE = 'DESCRIBE'
	FASTFORWARD = 'FASTFORWARD'
	BACKWARD = 'BACKWARD'
	
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2

	time_delay = 0.04
	clientInfo = {}
	
	def __init__(self, clientInfo):
		self.receiveType = ""
		self.clientInfo = clientInfo
		
	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			data = connSocket.recv(256)
			if data:
				print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))
	
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')
		
		# Process SETUP request
		if requestType == self.SETUP:
			self.receiveType = self.SETUP
			if self.state == self.INIT:
				# Update state
				print("processing SETUP\n")
				
				try:
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.clientInfo['videoTmp'] = VideoStream(filename)
					while self.clientInfo['videoTmp'].nextFrame():
						pass
					totalFrame = self.clientInfo['videoTmp'].frameNbr()
					fps = 1 / self.time_delay
					seconds = totalFrame / fps
					self.clientInfo['totalTime'] = str(timedelta(seconds=seconds))
					self.state = self.READY
				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1],self.receiveType,filename)
				
				# Generate a randomized RTSP session ID
				self.clientInfo['session'] = randint(100000, 999999)
				
				# Send RTSP reply
				self.replyRtsp(self.OK_200, seq[1],self.receiveType,filename)
				
				# Get the RTP/UDP port from the last line
				self.clientInfo['rtpPort'] = request[2].split(' ')[3]
		
		elif requestType == self.DESCRIBE:
			if self.state == self.READY:
				self.receiveType = self.DESCRIBE
				print("PROCESSING DESCRIBE\n")
				self.replyRtsp(self.OK_200, seq[1],self.receiveType,filename)

		# Process PLAY request
		elif requestType == self.PLAY:
			self.receiveType = self.PLAY
			if self.state == self.READY:
				print("processing PLAY\n")
				self.state = self.PLAYING
				
				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.replyRtsp(self.OK_200, seq[1],self.receiveType,filename)
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker'] = threading.Thread(target=self.sendRtp)
				self.clientInfo['worker'].start()
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
			self.receiveType = self.PAUSE
			if self.state == self.PLAYING:
				print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1],self.receiveType,filename)
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			self.receiveType = self.TEARDOWN
			print("processing TEARDOWN\n")

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1],self.receiveType,filename)
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()

		# Process FASTFORWARD request
		elif requestType == self.FASTFORWARD:
			if self.state == self.PLAYING:
				print("processing FASTFORWARD\n")
				self.clientInfo['videoStream'].fastForward()

		# Process BACKWARD request
		elif requestType == self.BACKWARD:
			if self.state == self.PLAYING:
				print("processing BACKWARD\n")
				self.clientInfo['videoStream'].fastBackward()
	def sendRtp(self):
		"""Send RTP packets over UDP."""
		while True:
			self.clientInfo['event'].wait(self.time_delay)
			
			# Stop sending if request is PAUSE or TEARDOWN
			if self.clientInfo['event'].isSet(): 
				break 
				
			data = self.clientInfo['videoStream'].nextFrame()
			if data: 
				frameNumber = self.clientInfo['videoStream'].frameNbr()
				frameSeq = self.clientInfo['videoStream'].frameSequence()
				try:
					address = self.clientInfo['rtspSocket'][1][0]
					port = int(self.clientInfo['rtpPort'])
					self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber,frameSeq),(address,port))
				except:
					print("Connection Error")
					#print('-'*60)
					#traceback.print_exc(file=sys.stdout)
					#print('-'*60)

	def makeRtp(self, payload, frameNbr,frameSeq):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26 # MJPEG type
		seqNum = frameSeq
		frameNum=frameNbr
		ssrc = 0 
		
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqNum,frameNum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq, type, filename):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			if type == self.DESCRIBE:
				reply = f"RTSP/1.0 200 OK\nCSeq: {seq}\nSession: {str(self.clientInfo['session'])}" \
						f"\n\nContent-Base: {filename}\nContent-Type: application/sdp\nContent-Length: {os.path.getsize(filename) / 1024} KB\n" \
						f"m=video 0 RTP/AVP 96\na=control:streamid=0\na=range:npt=0-7.741000\n" \
						f"a=length:npt=0-7.741000\na=trpmap:96 MP4V/SS44\na=AvgBitRate:integer:304018\na-StreamName:string:'hinted video track'"
				connSocket = self.clientInfo['rtspSocket'][0]
				connSocket.send(reply.encode())
			elif type == self.SETUP:
				reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session']) + '\nTotal_time: ' + str(self.clientInfo['totalTime'])
				connSocket = self.clientInfo['rtspSocket'][0]
				connSocket.send(reply.encode())
			else:
				# print "200 OK"
				reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
				connSocket = self.clientInfo['rtspSocket'][0]
				connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
