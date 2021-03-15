from gspreadWrapper import GspreadWrapper
from options import Options
from utils import Utils

from gspread.models import Cell
from gspread_formatting import *

class createVCAAggregate():
    def __init__(self):
        self.options = Options()
        self.utils = Utils()
        self.gspreadWrapper = GspreadWrapper()

    def loadVCAsFiles(self):
        masterDocument = self.gspreadWrapper.gc.open_by_key(self.options.VCAMasterFile)
        masterSheet = masterDocument.worksheet("Assessments")
        masterData = masterSheet.get_all_records()
        self.masterDataByIds = self.gspreadWrapper.groupById(masterData)
        self.vcaData = []
        for vcaFile in self.options.VCAsFiles:
            vcaDocument = self.gspreadWrapper.gc.open_by_key(vcaFile)
            vcaSheet = vcaDocument.worksheet("Assessments")
            data = vcaSheet.get_all_records()
            dataByIds = self.gspreadWrapper.groupById(data)
            self.vcaData.append(dataByIds)


    def createDoc(self):
        self.loadVCAsFiles()
        print('Create new document...')
        spreadsheet = self.gspreadWrapper.gc.create(self.options.VCAAggregateFileName)
        spreadsheet.share(
            self.options.accountEmail,
            perm_type='user',
            role='writer'
        )
        print('vCA aggregate document created.')

        print('Create sheet...')

        excludedAssessors = []
        validAssessments = []
        yellowAssessments = []
        assessments = []
        # Loop over master ids as reference
        for id in self.masterDataByIds:
            assessment = {}
            assessment[self.options.assessmentsIdColumn] = id
            assessment[self.options.assessorColumn] = self.masterDataByIds[id][self.options.assessorColumn]
            assessment[self.options.noVCAReviewsColumn] = 0
            assessment[self.options.fairColumn] = 0
            assessment[self.options.topQualityColumn] = 0
            assessment[self.options.profanityColumn] = 0
            assessment[self.options.scoreColumn] = 0
            assessment[self.options.copyColumn] = 0
            assessment[self.options.wrongChallengeColumn] = 0
            assessment[self.options.wrongCriteriaColumn] = 0
            assessment[self.options.otherColumn] = 0
            assessment[self.options.yellowCardColumn] = 0
            assessment[self.options.redCardColumn] = 0

            # Loop over all vca files
            for vcaFile in self.vcaData:
                assessment[self.options.noVCAReviewsColumn] = assessment[self.options.noVCAReviewsColumn] + self.checkIfReviewed(vcaFile[id])
                assessment[self.options.fairColumn] = assessment[self.options.fairColumn] + self.checkIfMarked(vcaFile[id], self.options.fairColumn)
                assessment[self.options.topQualityColumn] = assessment[self.options.topQualityColumn] + self.checkIfMarked(vcaFile[id], self.options.topQualityColumn)
                assessment[self.options.profanityColumn] = assessment[self.options.profanityColumn] + self.checkIfMarked(vcaFile[id], self.options.profanityColumn)
                assessment[self.options.scoreColumn] = assessment[self.options.scoreColumn] + self.checkIfMarked(vcaFile[id], self.options.scoreColumn)
                assessment[self.options.copyColumn] = assessment[self.options.copyColumn] + self.checkIfMarked(vcaFile[id], self.options.copyColumn)
                assessment[self.options.wrongChallengeColumn] = assessment[self.options.wrongChallengeColumn] + self.checkIfMarked(vcaFile[id], self.options.wrongChallengeColumn)
                assessment[self.options.wrongCriteriaColumn] = assessment[self.options.wrongCriteriaColumn] + self.checkIfMarked(vcaFile[id], self.options.wrongCriteriaColumn)
                assessment[self.options.otherColumn] = assessment[self.options.otherColumn] + self.checkIfMarked(vcaFile[id], self.options.otherColumn)

            (yellow, red) = self.calculateCards(assessment)
            assessment[self.options.yellowCardColumn] = yellow
            assessment[self.options.redCardColumn] = red

            if (red >= 1):
                excludedAssessors.append(assessment[self.options.assessorColumn])
            if (yellow >= 1):
                yellowAssessments.append(assessment)
            assessments.append(assessment)

        validAssessments = self.filterAssessments(yellowAssessments, excludedAssessors)

        self.gspreadWrapper.createSheetFromList(
            spreadsheet,
            'Aggregated',
            assessments,
            []
        )

        self.gspreadWrapper.createSheetFromList(
            spreadsheet,
            'Valid Assessments',
            validAssessments,
            [
                self.options.proposerMarkColumn, self.options.fairColumn,
                self.options.topQualityColumn, self.options.profanityColumn,
                self.options.scoreColumn, self.options.copyColumn,
                self.options.wrongChallengeColumn, self.options.wrongCriteriaColumn,
                self.options.otherColumn, self.options.otherRationaleColumn
            ]
        )

        worksheet = spreadsheet.get_worksheet(0)
        spreadsheet.del_worksheet(worksheet)

        print('Aggregated document created')

        print('Link: {}'.format(spreadsheet.url))

    def checkIfReviewed(self, row):
        if (
            (row[self.options.topQualityColumn] == 'x') or
            (row[self.options.fairColumn] == 'x') or
            (row[self.options.profanityColumn] == 'x') or
            (row[self.options.scoreColumn] == 'x') or
            (row[self.options.copyColumn] == 'x') or
            (row[self.options.wrongChallengeColumn] == 'x') or
            (row[self.options.wrongCriteriaColumn] == 'x') or
            (row[self.options.otherColumn] == 'x')
        ):
            return 1
        return 0

    def checkIfMarked(self, row, column):
        if (row[column] == 'x'):
            return 1
        return 0

    def calculateCards(self, row):
        yellow = 0
        red = 0
        tot = row[self.options.noVCAReviewsColumn]
        if (tot >= self.options.minimumVCA):
            if ((row[self.options.profanityColumn]/tot) >= self.options.profanityLimit):
                red = red + 1
            if ((row[self.options.scoreColumn]/tot) >= self.options.scoreLimit):
                yellow = yellow + 1
            if ((row[self.options.copyColumn]/tot) >= self.options.copyLimit):
                yellow = yellow + 1
            if ((row[self.options.wrongChallengeColumn]/tot) >= self.options.wrongChallengeLimit):
                yellow = yellow + 1
            if ((row[self.options.wrongCriteriaColumn]/tot) >= self.options.wrongCriteriaLimit):
                yellow = yellow + 1
            if ((row[self.options.otherColumn]/tot) >= self.options.otherLimit):
                yellow = yellow + 1
        return (yellow, red)

    def filterAssessments(self, yellowAssessments, excludedAssessors):
        filtered = []
        yellowRelatedTripletsIds = self.getRelatedTriplets(yellowAssessments)
        assessments = self.masterDataByIds
        for id in assessments:
            if id not in yellowRelatedTripletsIds:
                if (assessments[id][self.options.assessorColumn] not in excludedAssessors):
                    filtered.append(assessments[id])

        return filtered

    def getRelatedTriplets(self, yellowAssessments):
        return []




c = createVCAAggregate()
c.createDoc()