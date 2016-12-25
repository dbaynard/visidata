import string
import itertools
import pkg_resources
import re
import copy

import visidata
from . import vd, colors, options, status, error, WrongTypeStr, CalcErrorStr, moveListItem
from . import attrdict, values, date, anytype

from .tui import draw_clip, keyname, Key, Shift, Ctrl
from .Column import Column, ArrayNamedColumns
from .Path import Path

# A .. Z AA AB ...
defaultColNames = list(itertools.chain(string.ascii_uppercase, [''.join(i) for i in itertools.product(string.ascii_uppercase, repeat=2)]))

def load_commands():
    syscmds = pkg_resources.resource_filename(__name__, 'vd-syscmds.tsv')
    usercmds = options.userdir_prefix + 'vd-usercmds.tsv'

    vd().base_commands = Sheet('base_commands', Path(syscmds))
    vd().user_commands = Sheet('user_commands', Path(usercmds))

    from . import load_tsv  # must be after main import
    try:
        load_tsv(vd().base_commands, Path(syscmds).read_text(), header=True)
    except OSError as e:
        vd().status(str(e))
    except Exception as e:
        vd().exceptionCaught()

    try:
        load_tsv(vd().user_commands, Path(usercmds).read_text(), header=True)
    except OSError as e:
        pass  # vd().status(str(e))
    except Exception as e:
        vd().exceptionCaught()

    # set columns after load
    vd().base_commands.columns = ArrayNamedColumns(Sheet.help_colnames)
    vd().user_commands.columns = ArrayNamedColumns(Sheet.help_colnames)

def add_command(sheet_regex, prefixes, ch, execstr, helpstr):
    vd().base_commands.rows.append((sheet_regex, prefixes, keyname(ch), helpstr, execstr))

# must be done inside curses.initscr due to keyname
def setup_sheet_commands():
    def command(ch, cmdstr, helpstr):
        add_command('', '', ch, cmdstr, helpstr)
    def global_command(ch, cmdstr, helpstr):
        add_command('', 'g', ch, cmdstr, helpstr)

    load_commands()

    command(Key.F1,    'vd.push(SheetList(name + "_commands", sheet.commands, help_colnames[1:]))', 'open command help sheet')
    command(Key('q'),  'vd.sheets.pop(0)', 'quit the current sheet')

    command(Key.LEFT,  'cursorRight(-1)', 'go one column left')
    command(Key.DOWN,  'cursorDown(+1)', 'go one row down')
    command(Key.UP,    'cursorDown(-1)', 'go one row up')
    command(Key.RIGHT, 'cursorRight(+1)', 'go one column right')
    command(Key.NPAGE, 'cursorDown(nVisibleRows); sheet.topRowIndex += nVisibleRows', 'scroll one page down')
    command(Key.PPAGE, 'cursorDown(-nVisibleRows); sheet.topRowIndex -= nVisibleRows', 'scroll one page up')
    command(Key.HOME,  'sheet.topRowIndex = sheet.cursorRowIndex = 0', 'go to top row')
    command(Key.END,   'sheet.cursorRowIndex = len(rows)-1', 'go to last row')

    command(Key('h'), 'cursorRight(-1)', 'go one column left')
    command(Key('j'), 'cursorDown(+1)', 'go one row down')
    command(Key('k'), 'cursorDown(-1)', 'go one row up')
    command(Key('l'), 'cursorRight(+1)', 'go one column right')

    command(Shift.H, 'moveVisibleCol(cursorVisibleColIndex, max(cursorVisibleColIndex-1, 0)); sheet.cursorVisibleColIndex -= 1', 'move this column one left')
    command(Shift.J, 'sheet.cursorRowIndex = moveListItem(rows, cursorRowIndex, min(cursorRowIndex+1, nRows-1))', 'move this row one down')
    command(Shift.K, 'sheet.cursorRowIndex = moveListItem(rows, cursorRowIndex, max(cursorRowIndex-1, 0))', 'move this row one up')
    command(Shift.L, 'moveVisibleCol(cursorVisibleColIndex, min(cursorVisibleColIndex+1, nVisibleCols-1)); sheet.cursorVisibleColIndex += 1', 'move this column one right')

    command(Ctrl.G, 'status(statusLine)', 'show info for the current sheet')
    command(Ctrl.P, 'status(vd.statusHistory[0])', 'show previous status line again')
    command(Ctrl.V, 'status(initialStatus)', 'show version information')

    command(Key('t'), 'topRowIndex = cursorRowIndex', 'scroll cursor row to top of screen')
    command(Key('m'), 'topRowIndex = cursorRowIndex-int(nVisibleRows/2)', 'scroll cursor row to middle of screen')
    command(Key('b'), 'topRowIndex = cursorRowIndex-nVisibleRows+1', 'scroll cursor row to bottom of screen')

    command(Key('<'), 'skipUp()', 'skip up this column to previous value')
    command(Key('>'), 'skipDown()', 'skip down this column to next value')

    command(Key('_'), 'cursorCol.width = cursorCol.getMaxWidth(visibleRows)', 'set this column width to fit visible cells')
    command(Key('-'), 'cursorCol.width = 0', 'hide this column')
    command(Key('^'), 'cursorCol.name = cursorCol.getDisplayValue(cursorRow)', 'set this column header to this cell value')
    command(Key('!'), 'toggleKeyColumn(cursorColIndex)', 'toggle this column as a key column')

    command(Key('@'), 'cursorCol.type = date', 'set column type to ISO8601 datetime')
    command(Key('#'), 'cursorCol.type = int', 'set column type to integer')
    command(Key('$'), 'cursorCol.type = str', 'set column type to string')
    command(Key('%'), 'cursorCol.type = float', 'set column type to float')
    command(Key('~'), 'cursorCol.type = detectType(cursorValue)', 'autodetect type of column by its data')

    command(Key('['), 'rows.sort(key=lambda r,col=cursorCol: col.getValue(r))', 'sort by this column ascending')
    command(Key(']'), 'rows.sort(key=lambda r,col=cursorCol: col.getValue(r), reverse=True)', 'sort by this column descending')
    command(Ctrl.E, 'options.debug = True; error(vd.lastErrors[-1])', 'abort and print last error to terminal')
    command(Ctrl.D, 'options.debug = not options.debug; status("debug " + ("ON" if options.debug else "OFF"))', 'toggle debug mode')

    command(Shift.E, 'if vd.lastErrors: vd.push(SheetText("last_error", vd.lastErrors[-1]))', 'open stack trace for most recent error')
    command(Shift.F, 'vd.push(SheetFreqTable(sheet, cursorCol))', 'open frequency table from values in this column')

    command(Key('d'), 'rows.pop(cursorRowIndex)', 'delete this row')

    command(Shift.S, 'vd.push(Sheets(vd.sheets))', 'open Sheet stack')
    command(Shift.C, 'vd.push(SheetColumns(sheet))', 'open Columns for this sheet')
    command(Shift.O, 'vd.push(SheetDict("options", options.__dict__))', 'open Options')

    command(Key('/'), 'searchRegex(inputLine(prompt="/"), columns=[cursorCol], moveCursor=True)', 'search this column forward for regex')
    command(Key('?'), 'searchRegex(inputLine(prompt="?"), columns=[cursorCol], backward=True, moveCursor=True)', 'search this column backward for regex')
    command(Key('n'), 'searchRegex(columns=[cursorCol], moveCursor=True)', 'go to next match')
    command(Key('p'), 'searchRegex(columns=[cursorCol], backward=True, moveCursor=True)', 'go to previous match')

    command(Key(' '), 'toggle([cursorRow]); cursorDown(1)', 'toggle select of this row')
    command(Key('s'), 'select([cursorRow]); cursorDown(1)', 'select this row')
    command(Key('u'), 'unselect([cursorRow]); cursorDown(1)', 'unselect this row')
    command(Key('|'), 'select(sheet.rows[r] for r in searchRegex(inputLine(prompt="|"), columns=[cursorCol]))', 'select rows by regex in this column')
    command(Key('\\'), 'unselect(sheet.rows[r] for r in searchRegex(inputLine(prompt="\\\\"), columns=[cursorCol]))', 'unselect rows by regex in this column')

    command(Shift.R, 'sheet.filetype = inputLine("change type to: ", value=sheet.filetype)', 'set source type of this sheet')
    command(Ctrl.R, 'open_source(source, sheet.filetype); status("reloaded")', 'reload sheet from source')
    command(Ctrl.S, 'saveSheet(sheet, inputLine("save to: "))', 'save this sheet to new file')
    command(Key('o'), 'open_source(inputLine("open: "))', 'open local file or url')
    command(Ctrl.O, 'expr = inputLine("eval: "); push_pyobj(expr, eval(expr))', 'eval Python expression and open the result')

    command(Key('e'), 'cursorCol.setValue(cursorRow, editCell(cursorVisibleColIndex))', 'edit this cell')
    command(Key('c'), 'sheet.cursorVisibleColIndex = findColIdx(inputLine("goto column name: "), visibleCols)', 'goto visible column by name')
    command(Key('r'), 'sheet.cursorRowIndex = int(inputLine("goto row number: "))', 'goto row number')

    command(Key('='), 'addColumn(ColumnExpr(sheet, inputLine("new column expr=")), index=cursorColIndex+1)', 'add column by expr')
    command(Key(':'), 'addColumn(ColumnRegex(sheet, inputLine("new column regex:")), index=cursorColIndex+1)', 'add column by regex')
    command(Ctrl('^'), 'vd.sheets[0], vd.sheets[1] = vd.sheets[1], vd.sheets[0]', 'jump to previous sheet')
    command(Key.TAB,  'moveListItem(vd.sheets, 0, len(vd.sheets))', 'cycle through sheet stack')
    command(Key.BTAB, 'moveListItem(vd.sheets, -1, 0)', 'reverse cycle through sheet stack')

# when used with 'g' prefix
    global_command(Key.F1,   'vd.push(SheetAppend([vd.base_commands, vd.user_commands]))', 'open all commands sheet')
    global_command(Key('q'), 'vd.sheets.clear()', 'drop all sheets (clean exit)')

    global_command(Key('h'), 'sheet.cursorVisibleColIndex = sheet.leftVisibleColIndex = 0', 'go to leftmost column')
    global_command(Key('k'), 'sheet.cursorRowIndex = sheet.topRowIndex = 0', 'go to top row')
    global_command(Key('j'), 'sheet.cursorRowIndex = len(rows); sheet.topRowIndex = cursorRowIndex-nVisibleRows', 'go to bottom row')
    global_command(Key('l'), 'sheet.cursorVisibleColIndex = len(visibleCols)-1', 'go to rightmost column')

    global_command(Shift.H, 'moveListItem(columns, cursorColIndex, 0)', 'move this column all the way to the left')
    global_command(Shift.J, 'moveListItem(rows, cursorRowIndex, nRows)', 'move this row all the way to the bottom')
    global_command(Shift.K, 'moveListItem(rows, cursorRowIndex, 0)', 'move this row all the way to the top')
    global_command(Shift.L, 'moveListItem(columns, cursorColIndex, nCols)', 'move this column all the way to the right')

    global_command(Key('_'), 'for c in visibleCols: c.width = c.getMaxWidth(visibleRows)', 'set width of all columns to fit visible cells')
    global_command(Key('^'), 'for c in visibleCols: c.name = c.getDisplayValue(cursorRow)', 'set names of all visible columns to this row')
    global_command(Key('~'), 'for c in visibleCols: c.type = detectType(c.getValue(cursorRow))', 'autodetect types of all visible columns by their data')

    global_command(Shift.E, 'vd.push(SheetText("last_error", "\\n\\n".join(vd.lastErrors)))', 'open last 10 errors')

    global_command(Key('/'), 'searchRegex(inputLine(prompt="/"), moveCursor=True, columns=visibleCols)', 'search regex forward in all visible columns')
    global_command(Key('?'), 'searchRegex(inputLine(prompt="?"), backward=True, moveCursor=True, columns=visibleCols)', 'search regex backward in all visible columns')
    global_command(Key('n'), 'sheet.cursorRowIndex = max(searchRegex() or [cursorRowIndex])', 'go to first match')
    global_command(Key('p'), 'sheet.cursorRowIndex = min(searchRegex() or [cursorRowIndex])', 'go to last match')

    global_command(Key(' '), 'toggle(rows)', 'toggle select of all rows')
    global_command(Key('s'), 'select(rows)', 'select all rows')
    global_command(Key('u'), '_selectedRows.clear()', 'unselect all rows')

    global_command(Key('|'), 'select(sheet.rows[r] for r in searchRegex(inputLine(prompt="|"), columns=visibleCols))', 'select rows by regex in all visible columns')
    global_command(Key('\\'), 'unselect(sheet.rows[r] for r in searchRegex(inputLine(prompt="\\\\"), columns=visibleCols))', 'unselect rows by regex in all visible columns')

    global_command(Key('d'), 'sheet.rows = [r for r in sheet.rows if not sheet.isSelected(r)]; _selectedRows.clear()', 'delete all selected rows')

    global_command(Ctrl.P, 'vd.push(SheetText("statuses", vd.statusHistory))', 'open last 100 statuses')

    # experimental commands
    command(Key('"'), 'vd.push(vd.sheets[0].copy())', 'duplicate this sheet')



class Sheet:
    help_colnames = 'sheet_regex prefixes keystroke helpstr execstr'.split()
    def __init__(self, name, src=None):
        self.name = name
        self.filetype = None
        self.source = src
        self.rows = []
        self.cursorRowIndex = 0  # absolute index of cursor into self.rows
        self.cursorVisibleColIndex = 0  # index of cursor into self.visibleCols

        self.topRowIndex = 0     # cursorRowIndex of topmost row
        self.leftVisibleColIndex = 0    # cursorVisibleColIndex of leftmost column

        # as computed during draw()
        self.rowLayout = {}      # [rowidx] -> y
        self.visibleColLayout = {}      # [vcolidx] -> (x, w)

        # all columns in display order
        self.columns = []
        self.nKeys = 0           # self.columns[:nKeys] are all pinned to the left and matched on join

        # current search term
        self.currentRegex = None
        self.currentRegexColumns = None

        self._selectedRows = {}   # id(row) -> row

        # a list of attrdict specific to this sheet, composed from user_commands and base_commands
        self.commands = []

    def reload_commands(self):
        self.commands = []
        for commandset in [vd().user_commands, vd().base_commands]:
            for r in commandset.rows:
                v = values(r, commandset.columns)
                if not v.sheet_regex or re.match(v.sheet_regex, self.name):
                    self.commands.append(v)

    def copy(self):
        c = copy.copy(self)
        c.name += "'"
        c.topRowIndex = c.cursorRowIndex = 0
        c.leftVisibleColIndex = c.cursorVisibleColIndex = 0
        c.columns = copy.deepcopy(self.columns)
        return c

    def __repr__(self):
        return self.name

    def isSelected(self, r):
        return id(r) in self._selectedRows

    def command(self, keystroke, cmdstr, helpstr):
        add_command(self.name, '', keystroke, cmdstr, helpstr)

    def find_command(self, prefixes, keystroke):
        for cmd in self.commands:
            if cmd.prefixes == prefixes and cmd.keystroke == keystroke:
                return cmd

    def exec_command(self, vdglobals, prefixes, keystroke):
        cmd = self.find_command(prefixes, keystroke)
        if not cmd:
            vd().status('no command for "%s%s"' % (prefixes, keystroke))
            return

        # handy globals for use by commands
        self.vd = vd()
        self.sheet = self
        exec(cmd.execstr, vdglobals, dict((name, getattr(self, name)) for name in dir(self)))


    def findColIdx(self, colname, columns=None):
        if columns is None:
            columns = self.columns
        cols = list(colidx for colidx, c in enumerate(columns) if c.name == colname)
        if not cols:
            error('no column named "%s"' % colname)
        elif len(cols) > 1:
            status('%d columns named "%s"' % (len(cols), colname))
        return cols[0]

    def clipdraw(self, y, x, s, attr, w):
        return draw_clip(self.scr, y, x, s, attr, w)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name.replace(' ', '_')

    @property
    def nVisibleRows(self):
        return self.windowHeight-2

    @property
    def cursorCol(self):
        return self.visibleCols[self.cursorVisibleColIndex]

    @property
    def cursorRow(self):
        return self.rows[self.cursorRowIndex]

    @property
    def visibleRows(self):  # onscreen rows
        return self.rows[self.topRowIndex:self.topRowIndex+self.nVisibleRows]

    @property
    def visibleCols(self):  # non-hidden cols
        return [c for c in self.columns if not c.hidden]

    @property
    def cursorColIndex(self):
        return self.columns.index(self.cursorCol)

    @property
    def selectedRows(self):
        return [r for r in self.rows if id(r) in self._selectedRows]

    @property
    def keyCols(self):
        return self.columns[:self.nKeys]

    @property
    def keyColNames(self):
        return options.ch_KeySep.join(c.name for c in self.keyCols)

    @property
    def cursorValue(self):
        return self.cellValue(self.cursorRowIndex, self.cursorColIndex)

    @property
    def statusLine(self):
        return 'row %s/%s (%s selected); %d/%d columns visible' % (self.cursorRowIndex, len(self.rows), len(self._selectedRows), self.nVisibleCols, self.nCols)

    @property
    def nRows(self):
        return len(self.rows)

    @property
    def nCols(self):
        return len(self.columns)

    @property
    def nVisibleCols(self):
        return len(self.visibleCols)

    def moveVisibleCol(self, fromVisColIdx, toVisColIdx):
        fromColIdx = self.columns.index(self.visibleCols[fromVisColIdx])
        toColIdx = self.columns.index(self.visibleCols[toVisColIdx])
        moveListItem(self.columns, fromColIdx, toColIdx)
        return toVisColIdx

    def cursorDown(self, n):
        self.cursorRowIndex += n

    def cursorRight(self, n):
        self.cursorVisibleColIndex += n

    def cellValue(self, rownum, col):
        if not isinstance(col, Column):
            # assume it's the column number
            col = self.columns[col]
        return col.getValue(self.rows[rownum])

    def addColumn(self, col, index=None):
        if index is None:
            index = len(self.columns)
        if col:
            self.columns.insert(index, col)

    def toggleKeyColumn(self, colidx):
        if self.cursorColIndex >= self.nKeys: # if not a key, add it
            moveListItem(self.columns, self.cursorColIndex, self.nKeys)
            self.nKeys += 1
        else:  # otherwise move it after the last key
            self.nKeys -= 1
            moveListItem(self.columns, self.cursorColIndex, self.nKeys)

    def skipDown(self):
        pv = self.cursorValue
        for i in range(self.cursorRowIndex+1, len(self.rows)):
            if self.cellValue(i, self.cursorColIndex) != pv:
                self.cursorRowIndex = i
                return

        status('no different value down this column')

    def skipUp(self):
        pv = self.cursorValue
        for i in range(self.cursorRowIndex, -1, -1):
            if self.cellValue(i, self.cursorColIndex) != pv:
                self.cursorRowIndex = i
                return

        status('no different value up this column')

    def toggle(self, rows):
        for r in rows:
            if id(r) in self._selectedRows:
                del self._selectedRows[id(r)]
            else:
                self._selectedRows[id(r)] = r

    def select(self, rows):
        rows = list(rows)
        before = len(self._selectedRows)
        self._selectedRows.update(dict((id(r), r) for r in rows))
        status('selected %s/%s rows' % (len(self._selectedRows)-before, len(rows)))

    def unselect(self, rows):
        rows = list(rows)
        before = len(self._selectedRows)
        for r in rows:
            if id(r) in self._selectedRows:
                del self._selectedRows[id(r)]
        status('unselected %s/%s rows' % (before-len(self._selectedRows), len(rows)))

    def columnsMatch(self, row, columns, func):
        for c in columns:
            m = func(c.getDisplayValue(row))
            if m:
                return True
        return False

    def checkCursor(self):
        # keep cursor within actual available rowset
        if self.cursorRowIndex <= 0:
            self.cursorRowIndex = 0
        elif self.cursorRowIndex >= len(self.rows):
            self.cursorRowIndex = len(self.rows)-1

        if self.cursorVisibleColIndex <= 0:
            self.cursorVisibleColIndex = 0
        elif self.cursorVisibleColIndex >= self.nVisibleCols:
            self.cursorVisibleColIndex = self.nVisibleCols-1

        if self.topRowIndex <= 0:
            self.topRowIndex = 0
        elif self.topRowIndex > len(self.rows):
            self.topRowIndex = len(self.rows)-1

        # (x,y) is relative cell within screen viewport
        x = self.cursorVisibleColIndex - self.leftVisibleColIndex
        y = self.cursorRowIndex - self.topRowIndex + 1  # header

        # check bounds, scroll if necessary
        if y < 1:
            self.topRowIndex = self.cursorRowIndex
        elif y > self.nVisibleRows:
            self.topRowIndex = self.cursorRowIndex-self.nVisibleRows+1

        if x <= 0:
            self.leftVisibleColIndex = self.cursorVisibleColIndex
        else:
            while True:
                if self.leftVisibleColIndex == self.cursorVisibleColIndex: # not much more we can do
                    break
                self.calcColLayout()
                if self.cursorVisibleColIndex < min(self.visibleColLayout.keys()):
                    self.leftVisibleColIndex -= 1
                    continue
                elif self.cursorVisibleColIndex > max(self.visibleColLayout.keys()):
                    self.leftVisibleColIndex += 1
                    continue

                cur_x, cur_w = self.visibleColLayout[self.cursorVisibleColIndex]
                left_x, left_w = self.visibleColLayout[self.leftVisibleColIndex]
                if cur_x+cur_w < self.windowWidth: # current columns fit entirely on screen
                    break
                self.leftVisibleColIndex += 1

    def searchRegex(self, regex=None, columns=None, backward=False, moveCursor=False):
        'sets row index if moveCursor; otherwise returns list of row indexes'
        if regex:
            self.currentRegex = re.compile(regex, re.IGNORECASE)

        if not self.currentRegex:
            status('no regex')
            return []

        if columns:
            self.currentRegexColumns = columns

        if not self.currentRegexColumns:
            status('no columns given')
            return []

        if backward:
            rng = range(self.cursorRowIndex-1, -1, -1)
            rng2 = range(self.nRows-1, self.cursorRowIndex-1, -1)
        else:
            rng = range(self.cursorRowIndex+1, self.nRows)
            rng2 = range(0, self.cursorRowIndex+1)

        matchingRowIndexes = []

        for r in rng:
            if self.columnsMatch(self.rows[r], self.currentRegexColumns, self.currentRegex.search):
                if moveCursor:
                    self.cursorRowIndex = r
                    return r
                matchingRowIndexes.append(r)

        for r in rng2:
            if self.columnsMatch(self.rows[r], self.currentRegexColumns, self.currentRegex.search):
                if moveCursor:
                    self.cursorRowIndex = r
                    status('search wrapped')
                    return r
                matchingRowIndexes.append(r)

        status('%s matches for /%s/' % (len(matchingRowIndexes), self.currentRegex.pattern))

        return matchingRowIndexes

    def calcColLayout(self):
        self.visibleColLayout = {}
        x = 0
        for vcolidx in range(0, len(self.visibleCols)):
            col = self.visibleCols[vcolidx]
            if col.width is None:
                col.width = col.getMaxWidth(self.visibleRows)+len(options.ch_LeftMore)+len(options.ch_RightMore)
            if vcolidx < self.nKeys or vcolidx >= self.leftVisibleColIndex:  # visible columns
                self.visibleColLayout[vcolidx] = (x, min(col.width, self.windowWidth-x))
                x += col.width+len(options.ch_ColumnSep)
            if x > self.windowWidth-1:
                break

    def drawColHeader(self, vcolidx):
        # choose attribute to highlight column header
        if vcolidx == self.cursorVisibleColIndex:  # cursor is at this column
            hdrattr = colors[options.c_CurHdr]
        elif vcolidx < self.nKeys:
            hdrattr = colors[options.c_KeyCols]
        else:
            hdrattr = colors[options.c_Header]

        col = self.visibleCols[vcolidx]
        x, colwidth = self.visibleColLayout[vcolidx]

        # ANameTC
        typedict = {
                int: '#',
                str: '$',
                float: '%',
                date: '@',
                anytype: ' ',
            }
        T = typedict.get(col.type, '?')
        N = ' ' + (col.name or defaultColNames[vcolidx])  # save room at front for LeftMore
        if len(N) > colwidth-1:
            N = N[:colwidth-len(options.ch_Ellipsis)] + options.ch_Ellipsis
        self.clipdraw(0, x, N, hdrattr, colwidth)
        self.clipdraw(0, x+colwidth-len(T), T, hdrattr, len(T))

        if vcolidx == self.leftVisibleColIndex and vcolidx > self.nKeys:
            A = options.ch_LeftMore
            self.scr.addstr(0, x, A, colors[options.c_ColumnSep])

        C = options.ch_ColumnSep
        if x+colwidth+len(C) <= self.windowWidth:
            self.scr.addstr(0, x+colwidth, C, colors[options.c_ColumnSep])


    def draw(self, scr):
        numHeaderRows = 1
        self.scr = scr  # for clipdraw convenience
        scr.erase()  # clear screen before every re-draw

        self.windowHeight, self.windowWidth = scr.getmaxyx()
        sepchars = options.ch_ColumnSep
        if not self.columns:
            return status('no columns')

        self.rowLayout = {}
        self.calcColLayout()
        for vcolidx, colinfo in sorted(self.visibleColLayout.items()):
            x, colwidth = colinfo
            if x < self.windowWidth:  # only draw inside window
                self.drawColHeader(vcolidx)

                y = numHeaderRows
                for rowidx in range(0, self.nVisibleRows):
                    if self.topRowIndex + rowidx >= len(self.rows):
                        break

                    self.rowLayout[self.topRowIndex+rowidx] = y

                    row = self.rows[self.topRowIndex + rowidx]

                    if self.topRowIndex + rowidx == self.cursorRowIndex:  # cursor at this row
                        attr = colors[options.c_CurRow]
                    elif vcolidx < self.nKeys:
                        attr = colors[options.c_KeyCols]
                    else:
                        attr = colors[options.c_default]

                    if self.isSelected(row):
                        attr |= colors[options.c_SelectedRow]

                    if vcolidx == self.cursorVisibleColIndex:  # cursor is at this column
                        attr |= colors[options.c_CurCol]

                    cellval = self.visibleCols[vcolidx].getDisplayValue(row, colwidth-1)
                    self.clipdraw(y, x, options.ch_ColumnFiller + cellval, attr, colwidth)

                    if isinstance(cellval, CalcErrorStr):
                        self.clipdraw(y, x+colwidth-len(options.ch_Error), options.ch_Error, colors[options.c_Error], len(options.ch_Error))
                    elif isinstance(cellval, WrongTypeStr):
                        self.clipdraw(y, x+colwidth-len(options.ch_WrongType), options.ch_WrongType, colors[options.c_WrongType], len(options.ch_WrongType))

                    if x+colwidth+len(sepchars) <= self.windowWidth:
                       self.scr.addstr(y, x+colwidth, sepchars, attr or colors[options.c_ColumnSep])

                    y += 1

        if vcolidx+1 < self.nVisibleCols:
            self.scr.addstr(0, self.windowWidth-1, options.ch_RightMore, colors[options.c_ColumnSep])

    def editCell(self, vcolidx=None):
        if vcolidx is None:
            vcolidx = self.cursorVisibleColIndex
        x, w = self.visibleColLayout[vcolidx]
        y = self.rowLayout[self.cursorRowIndex]

        currentValue = self.cellValue(self.cursorRowIndex, vcolidx)
        r = vd().editText(y, x, w, value=currentValue, fillchar=options.ch_EditPadChar)
        return self.visibleCols[vcolidx].type(r)  # convert input to column type
