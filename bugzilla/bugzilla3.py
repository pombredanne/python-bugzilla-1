# bugzilla3.py - a Python interface to Bugzilla 3.x using xmlrpclib.
#
# Copyright (C) 2008, 2009 Red Hat Inc.
# Author: Will Woods <wwoods@redhat.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
# the full text of the license.

import bugzilla.base

class Bugzilla3(bugzilla.base.BugzillaBase):
    '''Concrete implementation of the Bugzilla protocol. This one uses the
    methods provided by standard Bugzilla 3.0.x releases.'''

    version = '0.1'
    user_agent = bugzilla.base.user_agent + ' Bugzilla3/%s' % version

    def __init__(self,**kwargs):
        bugzilla.base.BugzillaBase.__init__(self,**kwargs)
        self.user_agent = self.__class__.user_agent

    def _login(self,user,password):
        '''Backend login method for Bugzilla3'''
        return self._proxy.User.login({'login':user,'password':password})

    def _logout(self):
        '''Backend login method for Bugzilla3'''
        return self._proxy.User.logout()

    #---- Methods and properties with basic bugzilla info

    def _getuserforid(self,userid):
        '''Get the username for the given userid'''
        # STUB FIXME
        return str(userid)

    # Connect the backend methods to the XMLRPC methods
    def _getbugfields(self):
        '''Get a list of valid fields for bugs.'''
        # XXX BZ3 doesn't currently provide anything like the getbugfields()
        # method, so we fake it by looking at bug #1. Yuck.
        keylist = self._getbug(1).keys()
        if 'assigned_to' not in keylist:
            keylist.append('assigned_to')
        return keylist
    def _getproducts(self):
        '''This throws away a bunch of data that RH's getProdInfo
        didn't return. Ah, abstraction.'''
        product_ids = self._proxy.Product.get_accessible_products()
        r = self._proxy.Product.get_products(product_ids)
        return r['products']
    def _getcomponents(self,product):
        if type(product) == str:
            product = self._product_name_to_id(product)
        r = self._proxy.Bug.legal_values({'product_id':product,'field':'component'})
        return r['values']

    #---- Methods for reading bugs and bug info

    def _getbugs(self,idlist):
        '''Return a list of dicts of full bug info for each given bug id.
        bug ids that couldn't be found will return None instead of a dict.'''
        idlist = map(lambda i: int(i), idlist)
        r = self._proxy.Bug.get_bugs({'ids':idlist, 'permissive': 1})
        bugdict = dict([(b['id'], b['internals']) for b in r['bugs']])
        return [bugdict.get(i) for i in idlist]
    def _getbug(self,id):
        '''Return a dict of full bug info for the given bug id'''
        return self._getbugs([id])[0]
   # Bugzilla3 doesn't have getbugsimple - alias to the full method(s)
    _getbugsimple = _getbug
    _getbugssimple = _getbugs

    #---- createbug - call to create a new bug

    createbug_required = ('product','component','summary','version',
                          'op_sys','platform')
    def _createbug(self,**data):
        '''Raw xmlrpc call for createBug() Doesn't bother guessing defaults
        or checking argument validity. Use with care.
        Returns bug_id'''
        r = self._proxy.Bug.create(data)
        return r['id']

    #---- Methods for interacting with users

    def _createuser(self, email, name=None, password=None):
        '''Create a new bugzilla user directly.

        :arg email: email address for the new user
        :kwarg name: full name for the user
        :kwarg password: a password to use with the account
        '''
        userid = self._proxy.User.create(email, name, password)
        return userid

# Bugzilla 3.2 adds some new goodies on top of Bugzilla3.
class Bugzilla32(Bugzilla3):
    '''Concrete implementation of the Bugzilla protocol. This one uses the
    methods provided by standard Bugzilla 3.2.x releases.

    For further information on the methods defined here, see the API docs:
    http://www.bugzilla.org/docs/3.2/en/html/api/
    '''

    version = '0.1'
    user_agent = bugzilla.base.user_agent + ' Bugzilla32/%s' % version
    createbug_required = ('product','component','summary','version')

    def _addcomment(self,id,comment,private=False,
                   timestamp='',worktime='',bz_gid=''):
        '''Add a comment to the bug with the given ID. Other optional
        arguments are as follows:
            private:   if True, mark this comment as private.
            timestamp: Ignored by BZ32.
            worktime:  amount of time spent on this comment, in hours
            bz_gid:    Ignored by BZ32.
        '''
        return self._proxy.Bug.add_comment({'id':id,
                                            'comment':comment,
                                            'private':private,
                                            'work_time':worktime})

# Bugzilla 3.4 adds some new goodies on top of Bugzilla32.
class Bugzilla34(Bugzilla32):
    version = '0.2'
    user_agent = bugzilla.base.user_agent + ' Bugzilla34/%s' % version

    def _getusers(self, ids=None, names=None, match=None):
        '''Return a list of users that match criteria.

        :kwarg ids: list of user ids to return data on
        :kwarg names: list of user names to return data on
        :kwarg match: list of patterns.  Returns users whose real name or
            login name match the pattern.
        :raises xmlrpclib.Fault: Code 51: if a Bad Login Name was sent to the
                names array.
            Code 304: if the user was not authorized to see user they
                requested.
            Code 505: user is logged out and can't use the match or ids
                parameter.

        Available in Bugzilla-3.4+
        '''
        params = {}
        if ids:
            params['ids'] = ids
        if names:
            params['names'] = names
        if match:
            params['match'] = match
        if not params:
            raise bugzilla.base.NeedParamError('_get() needs one of ids,'
                    ' names, or match kwarg.')

        return self._proxy.User.get(params)

    def _query(self,query):
        '''Query bugzilla and return a list of matching bugs.
        query must be a dict with fields like those in in querydata['fields'].
        You can also pass in keys called 'quicksearch' or 'savedsearch' -
        'quicksearch' will do a quick keyword search like the simple search
        on the Bugzilla home page.
        'savedsearch' should be the name of a previously-saved search to
        execute. You need to be logged in for this to work.
        Returns a dict like this: {'bugs':buglist,
                                   'sql':querystring}
        buglist is a list of dicts describing bugs, and 'sql' contains the SQL
        generated by executing the search.
        You can also pass 'limit:[int]' to limit the number of results.
        For more info, see:
        http://www.bugzilla.org/docs/3.4/en/html/api/Bugzilla/WebService/Bug.html
        '''
        return self._proxy.Bug.search(query)

    def build_query(self,
                    product=None,
                    component=None,
                    version=None,
                    long_desc=None,
                    bug_id=None,
                    short_desc=None,
                    cc=None,
                    assigned_to=None,
                    reporter=None,
                    qa_contact=None,
                    status=None,
                    blocked=None,
                    dependson=None,
                    keywords=None,
                    keywords_type=None,
                    url=None,
                    url_type=None,
                    status_whiteboard=None,
                    status_whiteboard_type=None,
                    fixed_in=None,
                    fixed_in_type=None,
                    flag=None,
                    alias=None,
                    qa_whiteboard=None,
                    devel_whiteboard=None,
                    boolean_query=None,
                    bug_severity=None,
                    priority=None,
                    target_milestone=None,
                    emailtype="substring",
                    booleantype="substring"):
        """
        Build a query string from passed arguments. Will handle
        query parameter differences between various bugzilla versions.
        """

        def listify(val):
            if val is None:
                return val
            if type(val) is list:
                return val
            return [val]

        def add_boolean(value, key, bool_id):
            if value is None:
                return bool_id

            query["query_format"] = "advanced"
            for boolval in value:
                and_count = 0
                or_count = 0

                def make_bool_str(prefix):
                    return "%s%i-%i-%i" % (prefix, bool_id,
                                           and_count, or_count)

                for par in boolval.split(' '):
                    field = None
                    fval = par
                    typ = booleantype

                    if par.find('&') != -1:
                        and_count += 1
                    elif par.find('|') != -1:
                        or_count += 1
                    elif par.find('!') != -1:
                         query['negate%i' % bool_id] = 1
                    elif not key:
                        if par.find('-') == -1:
                            raise RuntimeError('Malformed boolean query: %s' %
                                               value)

                        args = par.split('-', 2)
                        field = args[0]
                        typ = args[1]
                        fval = None
                        if len(args) == 3:
                            fval = args[2]
                    else:
                        field = key

                    query[make_bool_str("field")] = field
                    if fval:
                        query[make_bool_str("value")] = fval
                    query[make_bool_str("type")] = typ

                bool_id += 1
            return bool_id

        if listify(component):
            component = ",".join(listify(component))

        query = {
            "product" : listify(product),
            "component" : component,
            "version" : version,
            "long_desc" : long_desc,
            "bug_id" : bug_id,
            "short_desc" : short_desc,
            "bug_status" : status,
            "keywords" : keywords,
            "keywords_type" : keywords_type,
            "bug_file_loc" : url,
            "bug_file_loc_type" : url_type,
            "status_whiteboard" : status_whiteboard,
            "status_whiteboard_type" : status_whiteboard_type,
            "fixed_in_type" : fixed_in_type,
            "bug_severity" : bug_severity,
            "priority" : priority,
            "target_milestone" : target_milestone
        }

        def add_email(value, key, count):
            if value is None:
                return count

            query["query_format"] = "advanced"
            query['email%i' % count] = value
            query['email%s%i' % (key, count)] = True
            query['emailtype%i' % count] = emailtype
            return count + 1

        email_count = 1
        email_count = add_email(cc, "cc", email_count)
        email_count = add_email(assigned_to, "assigned_to", email_count)
        email_count = add_email(reporter, "reporter", email_count)
        email_count = add_email(qa_contact, "qa_contact", email_count)

        chart_id = 0
        chart_id = add_boolean(fixed_in, "fixed_in", chart_id)
        chart_id = add_boolean(blocked, "blocked", chart_id)
        chart_id = add_boolean(dependson, "dependson", chart_id)
        chart_id = add_boolean(flag, "flagtypes.name", chart_id)
        chart_id = add_boolean(qa_whiteboard, "cf_qa_whiteboard", chart_id)
        chart_id = add_boolean(devel_whiteboard, "cf_devel_whiteboard",
                               chart_id)
        chart_id = add_boolean(alias, "alias", chart_id)
        chart_id = add_boolean(boolean_query, None, chart_id)

        # Strip out None elements in the dict
        for key in query.keys():
            if query[key] is None:
                del(query[key])
        return query


# Bugzilla 3.6 was released April 13, 2010
# XXX TODO probably more new methods from Bugzilla 3.6 we could use
class Bugzilla36(Bugzilla34):
    version = '0.1'
    user_agent = bugzilla.base.user_agent + ' Bugzilla36/%s' % version

    # Hooray, a proper _getbugfields implementation
    def _getbugfields(self):
        '''Get the list of valid fields for Bug objects'''
        r = self._proxy.Bug.fields({'include_fields':['name']})
        return [f['name'] for f in r['fields']]
        # NOTE: the RHBZ version lists 'comments' and 'groups', and strips
        # the 'cf_' from the beginning of custom fields.
