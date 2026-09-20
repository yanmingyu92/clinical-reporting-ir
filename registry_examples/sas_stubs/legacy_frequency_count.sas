/********************************************************************************
 * legacy_frequency_count.sas — SYNTHETIC STUB for public release
 *
 * Mimics the *structure* of a legacy frequency-count report macro
 * (parameter list, ODS RTF destination, output dataset) without containing
 * any production logic. Paired with the PUB-AE-OVERVIEW entry in
 * registry_examples/bridge_map_sample.yaml.
 ********************************************************************************/

%macro legacy_frequency_count(
    population_from  = ,          /* population dataset (denominators)   */
    population_where = ,          /* subsetting WHERE clause             */
    observation_from = ,          /* event/observation dataset           */
    observation_where= ,          /* event subsetting WHERE clause       */
    count_var        = ,          /* categorical variable to count       */
    therapy_cd_var   = TRTCD,     /* treatment code variable             */
    therapy_des_var  = TRTDES,    /* treatment description variable      */
    percent_incidence= Y,         /* Y = append (%) to each count        */
    output_fileref   = fptotb,    /* fileref for the RTF destination     */
    output_data      = work._freq_out,  /* count dataset                 */
    title_text_1     = ,
    subtitle         = ,
    end_notes        = ,
    data_source_txt  = ,
    debug            = N
);

    /* --- counts per treatment arm into an output dataset ------------------ */
    proc freq data=&observation_from. noprint;
        %if %length(&observation_where.) > 0 %then
            where &observation_where.;;
        tables &count_var. * &therapy_cd_var. /
               out=&output_data. (drop=percent) nocol norow;
    run;

    /* --- render to the ODS RTF destination -------------------------------- */
    ods rtf file=&output_fileref.;
    title1 "&title_text_1.";
    title2 "&subtitle.";
    footnote1 "&end_notes.";
    footnote2 "&data_source_txt.";

    proc report data=&output_data. nowd;
        column &count_var. &therapy_cd_var. count;
        define count / "n";
    run;

    ods rtf close;

    %if %upcase(&debug.) = Y %then %do;
        proc print data=&output_data.; run;
    %end;

%mend legacy_frequency_count;
