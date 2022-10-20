import _ from 'lodash';
import {
  getRowName,
  getTranslatedRowLabel,
  getSurveyFlatPaths,
  isRowSpecialLabelHolder,
  isRowProcessingEnabled,
} from 'js/assetUtils';
import {getColumnLabel} from 'js/components/submissions/tableUtils';
import {
  createEnum,
  SCORE_ROW_TYPE,
  RANK_LEVEL_TYPE,
  MATRIX_PAIR_PROPS,
  GROUP_TYPES_BEGIN,
  QUESTION_TYPES,
  CHOICE_LISTS,
} from 'js/constants';
import type {AnyRowTypeName} from 'js/constants';
import type {
  SurveyRow,
  SurveyChoice,
  SubmissionResponse,
  SubmissionAttachment,
  AssetResponse,
} from 'js/dataInterface';
import {
  getSupplementalPathParts,
  getSupplementalTranscriptPath,
  getSupplementalTranslationPath,
} from 'js/components/processing/processingUtils';
import type {LanguageCode} from 'js/components/languages/languagesStore';

export enum DisplayGroupTypeName {
  group_root = 'group_root',
  group_repeat = 'group_repeat',
  group_regular = 'group_regular',
  group_matrix = 'group_matrix',
  group_matrix_row = 'group_matrix_row',
}

export const DISPLAY_GROUP_TYPES = createEnum([
  DisplayGroupTypeName.group_root,
  DisplayGroupTypeName.group_repeat,
  DisplayGroupTypeName.group_regular,
  DisplayGroupTypeName.group_matrix,
  DisplayGroupTypeName.group_matrix_row,
]) as {[P in DisplayGroupTypeName]: DisplayGroupTypeName};

export class DisplayGroup {
  public type: DisplayGroupTypeName;
  /** Localized display label */
  public label: string | null = null;
  /** Unique identifier */
  public name: string | null = null;
  /** List of groups and responses */
  public children: Array<DisplayResponse|DisplayGroup> = [];

  constructor(
    type: DisplayGroupTypeName,
    label?: string | null,
    name?: string | null
  ) {
    this.type = type;
    if (label) {
      this.label = label;
    }
    if (name) {
      this.name = name;
    }
  }

  addChild(child: DisplayResponse|DisplayGroup) {
    this.children.push(child);
  }
}

export class DisplayResponse {
  /** One of QUESTION_TYPES or `null` for supplemental details */
  public type: AnyRowTypeName | null;
  /** Localized display label */
  public label: string | null;
  /** Unique identifier */
  public name: string;
  /**
   * Unique identifier of a choices list, only applicable for question types
   * that uses choices lists.
   */
  public listName: string | undefined;
  /** User response, `null` for no response */
  public data: string | null = null;

  constructor(
    type: AnyRowTypeName | null,
    label: string | null,
    name: string,
    listName: string | undefined,
    data?: string | null
  ) {
    this.type = type;
    this.label = label;
    this.name = name;
    if (data) {
      this.data = data;
    }
    if (listName) {
      this.listName = listName;
    }
  }
}

/**
 * Returns a sorted object of transcript/translation keys
 */
export function sortAnalysisFormJsonKeys (analysis_form_json: any) {
  let additionalFields: {source: string, dtpath: string}[] = analysis_form_json.additional_fields;
  let sortedBySource: {[key: string]: string[]} = {};

  additionalFields.forEach((afParams) => {
    let expandedPath = `_supplementalDetails/${afParams.dtpath}`;
    if (!sortedBySource[afParams.source]) {
      sortedBySource[afParams.source] = [];
    }
    sortedBySource[afParams.source].push(expandedPath);
  });
  return sortedBySource;
}

/**
 * Returns a root group with everything inside
 */
export function getSubmissionDisplayData(
  asset: AssetResponse,
  /** for choosing label to display */
  translationIndex: number,
  submissionData: SubmissionResponse
) {
  // let's start with a root of survey being a group with special flag
  const output = new DisplayGroup(DISPLAY_GROUP_TYPES.group_root);

  const survey = asset?.content?.survey || []
  const choices = asset?.content?.choices || []

  const flatPaths = getSurveyFlatPaths(survey, true);

  let supplementalDetailKeys = sortAnalysisFormJsonKeys(asset.analysis_form_json);
  /**
   * Recursively generates a nested architecture of survey with data.
   */
  function traverseSurvey(
    /** Rows and groups will be added to it as children. */
    parentGroup: DisplayGroup,
    /** The submissionData scoped by parent (useful for repeat groups). */
    parentData: SubmissionResponse,
    /** Inside a repeat group this is the current repeat submission index. */
    repeatIndex: number | null = null
  ) {
    for (let rowIndex = 0; rowIndex < survey.length; rowIndex++) {
      const row = survey[rowIndex];

      const rowName = getRowName(row);
      let rowListName = getRowListName(row);
      const rowLabel = getTranslatedRowLabel(rowName, survey, translationIndex);

      let parentGroupPath = null;
      if (parentGroup.name !== null) {
        parentGroupPath = flatPaths[parentGroup.name];
      }

      let isRowCurrentLevel = isRowFromCurrentGroupLevel(
        rowName,
        parentGroupPath,
        survey
      );

      // we are interested only in questions from this group level
      if (!isRowCurrentLevel) {
        continue;
      }
      // let's hide rows that don't carry any submission data
      if (
        row.type === QUESTION_TYPES.note.id ||
        row.type === QUESTION_TYPES.hidden.id
      ) {
        continue;
      }
      /*
       * For a complex form items (e.g. rating) Backend constructs a pair of
       * group and a row. The row serves a purpose of a label and we don't want
       * it here as `getTranslatedRowLabel` handles this already. We check
       * previous row.
       */
      if (isRowSpecialLabelHolder(survey[rowIndex - 1], row)) {
        continue;
      }

      let rowData = getRowData(rowName, survey, parentData);

      if (row.type === GROUP_TYPES_BEGIN.begin_repeat) {
        if (Array.isArray(rowData)) {
          rowData.forEach((item, itemIndex) => {
            let itemObj = new DisplayGroup(
              DISPLAY_GROUP_TYPES.group_repeat,
              rowLabel,
              rowName
            );
            parentGroup.addChild(itemObj);
            /*
             * Start whole process again starting at this place in survey,
             * with current group as parent element and new repeat index
             * being used.
             */
            traverseSurvey(itemObj, item, itemIndex);
          });
        }
      } else if (row.type === GROUP_TYPES_BEGIN.begin_kobomatrix) {
        let matrixGroupObj = new DisplayGroup(
          DISPLAY_GROUP_TYPES.group_matrix,
          rowLabel,
          rowName,
        );
        parentGroup.addChild(matrixGroupObj);

        if (Array.isArray(choices)) {
          /*
           * For matrixes we generate a group of subgroups - each subgroup
           * corresponds to a matrix item from choices.
           */
          choices.forEach((item) => {
            if (
              item[MATRIX_PAIR_PROPS.inChoices as keyof SurveyChoice] ===
              row[MATRIX_PAIR_PROPS.inSurvey as keyof SurveyRow]
            ) {
              // Matrix is only one level deep, so we can use a "simpler"
              // non-recursive special function
              populateMatrixData(
                survey,
                choices,
                submissionData,
                translationIndex,
                matrixGroupObj,
                getRowName(item),
                parentData
              );
            }
          });
        }
      } else if (
        row.type === GROUP_TYPES_BEGIN.begin_group ||
        row.type === GROUP_TYPES_BEGIN.begin_score ||
        row.type === GROUP_TYPES_BEGIN.begin_rank
      ) {
        let rowObj = new DisplayGroup(
          DISPLAY_GROUP_TYPES.group_regular,
          rowLabel,
          rowName,
        );
        parentGroup.addChild(rowObj);
        /*
         * Start whole process again starting at this place in survey,
         * with current group as parent element and pass current repeat index.
         */
        traverseSurvey(rowObj, rowData, repeatIndex);
      } else if (
        Object.keys(QUESTION_TYPES).includes(row.type) ||
        row.type === SCORE_ROW_TYPE ||
        row.type === RANK_LEVEL_TYPE
      ) {
        // for repeat groups, we are interested in current repeat item's data
        if (Array.isArray(rowData) && repeatIndex !== null) {
          rowData = rowData[repeatIndex];
        }

        // score and rank don't have list name on them and they need to use
        // the one of their parent
        if (row.type === SCORE_ROW_TYPE || row.type === RANK_LEVEL_TYPE) {
          const parentGroupRow = survey.find((row) =>
            getRowName(row) === parentGroup.name
          );
          rowListName = getRowListName(parentGroupRow);
        }

        let rowObj = new DisplayResponse(
          row.type,
          rowLabel,
          rowName,
          rowListName,
          rowData
        );
        parentGroup.addChild(rowObj);

        /*
        getRowSupplementalResponses(
          asset,
          submissionData,
          rowName,
        ).forEach((resp) => {parentGroup.addChild(resp)})
        */
        let rowqpath = flatPaths[rowName].replace(/\//g, '-');
        supplementalDetailKeys[rowqpath]?.forEach((sdKey: string) => {
          parentGroup.addChild(
            new DisplayResponse(null,
              getColumnLabel(asset, sdKey, false),
              sdKey,
              undefined,
              getSupplementalDetailsContent(submissionData, sdKey),
            )
          );
        })
      }
    }
  }
  traverseSurvey(output, submissionData);

  return output;
}

/**
 * It creates display data structure for a given choice-row of a Matrix.
 * As the data is bit different from all other question types, we need to use
 * a special function, not a great traverseSurvey one.
 */
function populateMatrixData(
  survey: SurveyRow[],
  choices: SurveyChoice[],
  submissionData: SubmissionResponse,
  translationIndex: number,
  /** A group you want to add a row of questions to. */
  matrixGroup: DisplayGroup,
  /** The row name. */
  matrixRowName: string,
  /** The submissionData scoped by parent (useful for repeat groups). */
  parentData: SubmissionResponse
) {
  // This should not happen, as the only DisplayGroup with null name will be of
  // the group_root type, but we need this for the types.
  if (matrixGroup.name === null) {
    return
  }

  // create row display group and add it to matrix group
  const matrixRowLabel = getTranslatedRowLabel(matrixRowName, choices, translationIndex);
  let matrixRowGroupObj = new DisplayGroup(
    DISPLAY_GROUP_TYPES.group_matrix_row,
    matrixRowLabel,
    matrixRowName,
  );
  matrixGroup.addChild(matrixRowGroupObj);

  const flatPaths = getSurveyFlatPaths(survey, true);
  const matrixGroupPath = flatPaths[matrixGroup.name];

  /*
   * Iterate over survey rows to find only ones from inside the matrix.
   * These rows are the questions from the target matrix choice-row, so we find
   * all neccessary pieces of data nd build display data structure for it.
   */
  Object.keys(flatPaths).forEach((questionName) => {
    if (flatPaths[questionName].startsWith(`${matrixGroupPath}/`)) {
      const questionSurveyObj = survey.find((row) =>
        getRowName(row) === questionName
      );
      // We are only interested in going further if object was found.
      if (typeof questionSurveyObj === 'undefined') {
        return;
      }

      /*
       * NOTE: Submission data for a Matrix question is kept in an unusal
       * property, so instead of:
       * [PATH/]MATRIX/MATRIX_QUESTION
       * it is stored in:
       * [PATH/]MATRIX_CHOICE/MATRIX_CHOICE_QUESTION
       */
      let questionData = null;
      const dataProp = `${matrixGroupPath}_${matrixRowName}/${matrixGroup.name}_${matrixRowName}_${questionName}`;
      if (submissionData[dataProp]) {
        questionData = submissionData[dataProp];
      } else if (parentData[dataProp]) {
        /*
         * If Matrix question is inside a repeat group, the data is stored
         * elsewhere :tableflip:
         */
        questionData = parentData[dataProp];
      }

      let questionObj = new DisplayResponse(
        questionSurveyObj.type,
        getTranslatedRowLabel(questionName, survey, translationIndex),
        questionName,
        getRowListName(questionSurveyObj),
        questionData
      );
      matrixRowGroupObj.addChild(questionObj);
    }
  });
}

/**
 * Returns data for given row, works for groups too. Returns `null` for no
 * answer, array for repeat groups and object for regular groups
 */
export function getRowData(
  name: string,
  survey: SurveyRow[],
  data: SubmissionResponse
) {
  if (data === null || typeof data !== 'object') {
    return null;
  }

  const flatPaths = getSurveyFlatPaths(survey, true);
  const path = flatPaths[name];

  if (data[path]) {
    return data[path];
  } else if (data[name]) {
    return data[name];
  } else if (path) {
    // we don't really know here if this is a repeat or a regular group
    // so we let the data be the guide (possibly not trustworthy)
    const repeatRowData = getRepeatGroupAnswers(data, path);
    if (repeatRowData.length >= 1) {
      return repeatRowData;
    }

    const rowData = getRegularGroupAnswers(data, path);
    if (Object.keys(rowData).length >= 1) {
      return rowData;
    }
  }
  return null;
}

/**
 * Tells if given row is an immediate child of given group
 */
function isRowFromCurrentGroupLevel(
  rowName: string,
  /** Null for root level rows. */
  groupPath: string|null,
  survey: SurveyRow[]
) {
  const flatPaths = getSurveyFlatPaths(survey, true);
  if (groupPath === null) {
    return flatPaths[rowName] === rowName;
  } else {
    return flatPaths[rowName] === `${groupPath}/${rowName}`;
  }
}

/**
 * Returns an array of answers
 */
export function getRepeatGroupAnswers(
  data: SubmissionResponse,
  /** With groups e.g. group_person/group_pets/group_pet/pet_name. */
  targetKey: string
) {
  const answers: string[] = [];

  // Goes through nested groups from key, looking for answers.
  const lookForAnswers = (data: SubmissionResponse, levelIndex: number) => {
    const levelKey = targetKey.split('/').slice(0, levelIndex + 1).join('/');
    // Each level could be an array of repeat group answers or object with questions.
    if (levelKey === targetKey) {
      if (Object.prototype.hasOwnProperty.call(data, targetKey)) {
        answers.push(data[targetKey]);
      }
    } else if (Array.isArray(data[levelKey])) {
      data[levelKey].forEach((item: SubmissionResponse) => {
        lookForAnswers(item, levelIndex + 1);
      });
    }
  };

  lookForAnswers(data, 0);

  return answers;
}

/**
 * Filters data for items inside the group
 */
function getRegularGroupAnswers(
  data: SubmissionResponse,
  /** With groups e.g. group_person/group_pets/group_pet. */
  targetKey: string
) {
  const answers: {[questionName: string]: any} = {};
  Object.keys(data).forEach((objKey) => {
    if (objKey.startsWith(`${targetKey}/`)) {
      answers[objKey] = data[objKey];
    }
  });
  return answers;
}

function getRowListName(row: SurveyRow | undefined): string | undefined {
  let returnVal;
  if (row && Object.keys(row).includes(CHOICE_LISTS.SELECT)) {
    returnVal = row[CHOICE_LISTS.SELECT as keyof SurveyRow];
  }
  if (row && Object.keys(row).includes(CHOICE_LISTS.MATRIX)) {
    returnVal = row[CHOICE_LISTS.MATRIX as keyof SurveyRow];
  }
  if (row && Object.keys(row).includes(CHOICE_LISTS.SCORE)) {
    returnVal = row[CHOICE_LISTS.SCORE as keyof SurveyRow];
  }
  if (row && Object.keys(row).includes(CHOICE_LISTS.RANK)) {
    returnVal = row[CHOICE_LISTS.RANK as keyof SurveyRow];
  }
  if (typeof returnVal === 'string') {
    return returnVal;
  }
  return undefined;
}

/**
 * Returns an attachment object or an error message.
 */
export function getMediaAttachment(
  submission: SubmissionResponse,
  fileName: string
): string | SubmissionAttachment {
  const validFileName = getValidFilename(fileName);
  let mediaAttachment: string | SubmissionAttachment = t('Could not find ##fileName##').replace(
    '##fileName##',
    fileName,
  );

  submission._attachments.forEach((attachment) => {
    if (attachment.filename.includes(validFileName)) {
      mediaAttachment = attachment;
    }
  });

  return mediaAttachment;
}

/**
 * Returns supplemental details for given path,
 * e.g. `_supplementalDetails/question_name/transcript_pl` or
 * e.g. `_supplementalDetails/question_name/translated_pl`.
 *
 * NOTE: transcripts are actually not nested on language level (because there
 * can be only one transcript), but we need to use paths with languages in it
 * to build Submission Modal and Data Table properly.
 */
export function getSupplementalDetailsContent(
  submission: SubmissionResponse,
  path: string
) {
  const pathArray = path.split('/');
  const pathParts = getSupplementalPathParts(path);

  // Separate route for getting transcripts value.
  if (pathParts.isTranscript) {
    // There is always one transcript, not nested in language code object, thus
    // we don't need the language code in the last element of the path.
    pathArray.pop();
    pathArray.push('transcript');
    const transcriptObj = _.get(submission, pathArray, '');
    if (
      transcriptObj.languageCode === pathParts.languageCode &&
      typeof transcriptObj.value === 'string'
    ) {
      return transcriptObj.value;
    }
    return t('N/A');
  }

  // The last element is `translated_<language code>`, but we don't want
  // the underscore to be there.
  pathArray.pop();
  pathArray.push('translation');
  pathArray.push(pathParts.languageCode);

  // Then we add one more nested level
  pathArray.push('value');
  // Moments like these makes you really apprecieate the beauty of lodash.
  const value = _.get(submission, pathArray, '');
  // If there is no value it could be either WIP or intentional. We want to be
  // clear about the fact it could be intentionally empty.
  return value || t('N/A');
}

/**
 * Returns all supplemental details (as rows) for given row. Includes transcript
 * and all translations.
 *
 * Returns empty array if row is not enabled to have supplemental details.
 *
 * If there is potential for details, then it will return a full list of
 * DisplayResponses with existing values (falling back to empty strings).
 */
export function getRowSupplementalResponses(
  asset: AssetResponse,
  submissionData: SubmissionResponse,
  rowName: string,
): DisplayResponse[] {
  const output: DisplayResponse[] = [];
  if (isRowProcessingEnabled(asset.uid, rowName)) {
    const advancedFeatures = asset.advanced_features;

    if (advancedFeatures.transcript?.languages !== undefined) {
      advancedFeatures.transcript.languages.forEach((languageCode: LanguageCode) => {
        const path = getSupplementalTranscriptPath(rowName, languageCode);
        output.push(
          new DisplayResponse(
            null,
            getColumnLabel(asset, path, false),
            path,
            undefined,
            getSupplementalDetailsContent(submissionData, path)
          )
        );
      });
    }

    if (advancedFeatures.translation?.languages !== undefined) {
      advancedFeatures.translation.languages.forEach((languageCode: LanguageCode) => {
        const path = getSupplementalTranslationPath(rowName, languageCode);
        output.push(
          new DisplayResponse(
            null,
            getColumnLabel(asset, path, false),
            path,
            undefined,
            getSupplementalDetailsContent(submissionData, path)
          )
        );
      });
    }
  }

  return output;
}

/**
 * Mimics Django get_valid_filename() to match back-end renaming when an
 * attachment is saved in storage.
 * See https://github.com/django/django/blob/832adb31f27cfc18ad7542c7eda5a1b6ed5f1669/django/utils/text.py#L224
 */
export function getValidFilename(
  fileName: string
): string {
  return fileName.normalize('NFD').replace(/\p{Diacritic}/gu, '')
    .replace(/ /g, '_')
    .replace(/[^\p{L}\p{M}\.\d_-]/gu, '');
}

export default {
  DISPLAY_GROUP_TYPES,
  getSubmissionDisplayData,
  getRepeatGroupAnswers,
};
