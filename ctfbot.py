import requests, json, sys
from datetime import date
from settings import SERVER, PORT, CHANNEL, NICKNAME
from twisted.internet import defer, endpoints, protocol, reactor, task
from twisted.python import log
from twisted.words.protocols import irc


class CTFTimerBot(irc.IRCClient):
    nickname = NICKNAME
    
    # API URLS
    upcomming_ctfs = "https://ctftime.org/api/v1/events/"
    top10_teams = "https://ctftime.org/api/v1/top/"
    teams_info = "https://ctftime.org/api/v1/teams/"

    def __init__(self):
        self.deferred = defer.Deferred()

    def connectionLost(self, reason):
        self.deferred.errback(reason)

    def signedOn(self):
        #for channel in self.factory.channels:
        self.join(self.factory.channel)

    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        message = message.strip()
        if not message.startswith('!'):              return  
        command, sep, rest = message.lstrip('!').partition(' ')
        func = getattr(self, 'command_' + command, None)
        
        if func is None:
            return
        d = defer.maybeDeferred(func, rest)
        d.addErrback(self._showError)
        if channel == self.nickname:
            d.addCallback(self._sendMessage, nick)
        else:
            d.addCallback(self._sendMessage, channel, nick)

    def _sendMessage(self, msg, target, nick=None):
        if nick:
            msg = '%s, %s' % (nick, msg)
        self.msg(target, msg)

    def _showError(self, failure):
        return failure.getErrorMessage()

    def command_upcoming(self, rest):
        """
        Returns list of upcomming CTFs
        """
        response = requests.get(self.upcomming_ctfs)
        for event in response.json():
            event_info = "Name: {}, Format: {}, Date: {} - {}, Weight: {} ".format(event['title'].encode("utf-8"), event['format'].encode("utf-8"), event['start'], event['finish'], event['weight'])
            self._sendMessage(event_info, self.factory.channel)
        return 'nn'
    
    def command_top10(self, rest):
        response = requests.get(self.top10_teams)
        year = rest.partition(' ')

        if not year[0] == '':
            teams = response.json()[str(year[0])]
        else:
            teams = response.json()[str(date.today().year)]

        for team in teams:
            team_info = "Name: {}, Points: {}".format(team['team_name'].encode("utf-8"), team['points'])
            self._sendMessage(team_info, self.factory.channel)
        return "tt"

    def command_ping(self, rest):
        return 'Pong.'

    def command_saylater(self, rest):
        when, sep, msg = rest.partition(' ')
        when = int(when)
        d = defer.Deferred()
        reactor.callLater(when, d.callback, msg)
        return d


class CTFTimerFactory(protocol.ReconnectingClientFactory):
    protocol = CTFTimerBot
    channel  = CHANNEL
    #channels = ['#denkei']


def main(reactor, description):
    endpoint = endpoints.clientFromString(reactor, description)
    factory = CTFTimerFactory()
    d = endpoint.connect(factory)
    d.addCallback(lambda protocol: protocol.deferred)
    return d


if __name__ == '__main__':
    log.startLogging(sys.stderr)
    task.react(main, ['tcp:{}:{}'.format(SERVER, PORT)])
