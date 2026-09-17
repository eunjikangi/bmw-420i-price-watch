"""robots.txt matching with longest-rule precedence (RFC 9309)."""
import re
from urllib.parse import urlsplit, unquote

class RobotsPolicy:
    def set_url(self, url):
        self.url = url

    def parse(self, lines):
        self.groups = []
        agents, rules = [], []
        had_rules = False
        def flush():
            if agents:
                self.groups.append((list(agents), list(rules)))
        for raw in lines:
            line = raw.split('#', 1)[0].strip()
            if ':' not in line:
                continue
            name, value = (x.strip() for x in line.split(':', 1))
            name = name.lower()
            if name == 'user-agent':
                if had_rules:
                    flush(); agents, rules, had_rules = [], [], False
                agents.append(value.lower())
            elif name in ('allow', 'disallow') and agents:
                had_rules = True
                if value:
                    rules.append((name == 'allow', unquote(value)))
        flush()

    def can_fetch(self, agent, url):
        matches = []
        for agents, rules in self.groups:
            specificity = max((len(a) for a in agents if a != '*' and a in agent.lower()), default=0)
            if specificity or '*' in agents:
                matches.append((specificity, rules))
        if not matches:
            return True
        best_group = max(s for s, _ in matches)
        p = urlsplit(url)
        path = unquote(p.path or '/') + ('?' + unquote(p.query) if p.query else '')
        matches_rules = []
        for spec, rules in matches:
            if spec != best_group:
                continue
            for allowed, rule in rules:
                tail = rule.endswith('$')
                body = rule[:-1] if tail else rule
                pattern = '^' + re.escape(body).replace(r'\*', '.*') + ('$' if tail else '')
                if re.search(pattern, path):
                    matches_rules.append((len(body.replace('*', '').encode('utf-8')), allowed))
        if not matches_rules:
            return True
        # An equally specific Allow wins; an early Allow: / never hides a longer Disallow.
        return max(matches_rules)[1]

