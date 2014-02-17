
class UserMapper():
	_userMap = {
			# 'linuxninja39': {
			# 	'password': 'x',
			# 	'remoteUser': 'linuxninja39.aTester',
			# 	'remotePassword': 'x'
			# 	}
			}
	def getUser(self, user, pw):
		if self._userMap[user]:
			if self._userMap[user]['password'] == pw:
				return self._userMap[user]
		else:
			return False;

